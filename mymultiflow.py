
#-------------------------------------------------------------------------
# FILE:             mymultiflow.py
# DESCRIPTION:      Size-Based Dynamic DMZ OpenFlow Controller
# AUTHORS:          Haotian Wu, Richard Habeeb
#-------------------------------------------------------------------------

#-------------------------------------------------------------------------
# IMPORTS
#-------------------------------------------------------------------------
from pox.core import core
from pox.openflow import *
from pox.lib.addresses import *
from pox.lib.util import dpid_to_str
from pox.lib.util import str_to_bool
import pox.openflow.libopenflow_01 as of
from flask import Flask
from flask import render_template
import json
import logging
import random
from utils import *
import time
import datetime
import threading


#-------------------------------------------------------------------------
# CONSTANTS
#-------------------------------------------------------------------------
FLOW_STATS_INTERVAL_SECS = 1
THRESHOLD_BITS_PER_SEC = 500 * 1024 * 1024
FLOW_ENTRY_IDLE_TIMEOUT_SECS = 10
FLOW_ENTRY_HARD_TIMEOUT_SECS = 800
RANDOM_TIMEOUT = { 'min': 3, 'max': 10 }

#-------------------------------------------------------------------------
# VARIABLES
#-------------------------------------------------------------------------
flask_log = logging.getLogger('werkzeug')
flask_log.setLevel(logging.ERROR)

log = core.getLogger()

# We don't want to flood immediately when a switch connects.
# Can be overriden on commandline.
_flood_delay = 0

#-------------------------------------------------------------------------
# CLASSES
#-------------------------------------------------------------------------


class Flow(object):
    RUNNING_AVERAGE_WINDOW = 1

    def __init__(self, match=None):
        self.network_layer_src = None
        self.network_layer_dst = None
        self.transport_layer_src = None
        self.transport_layer_dst = None
        self.hardware_port = None
        self.match = match
        if(match is not None and
                hasattr(match, 'nw_src') and
                hasattr(match, 'nw_dst') and
                hasattr(match, 'tp_src') and
                hasattr(match, 'tp_dst') and
                hasattr(match, 'in_port')):
            self.network_layer_src = match.nw_src
            self.network_layer_dst = match.nw_dst
            self.transport_layer_src = match.tp_src
            self.transport_layer_dst = match.tp_dst
            self.hardware_port = match.in_port

        self.bit_rates = [0] * Flow.RUNNING_AVERAGE_WINDOW
        self.running_rate_sum = 0
        self.total_bytes = 0

    def __eq__(self, other):
        if other is None:
            return False
        return \
            self.network_layer_src == other.network_layer_src and \
            self.network_layer_dst == other.network_layer_dst and \
            self.tranport_layer_src == other.tranport_layer_src and \
            self.tranport_layer_dst == other.tranport_layer_dst and \
            self.hardware_port == other.hardware_port

    def get_flow_table_mod_msg(self, port):
        msg = of.ofp_flow_mod()
        msg.match = self.match
        msg.actions.append(of.ofp_action_output(port=port))
        msg.command = of.OFPFC_MODIFY
        msg.idle_timeout = FLOW_ENTRY_IDLE_TIMEOUT_SECS
        msg.hard_timeout = FLOW_ENTRY_HARD_TIMEOUT_SECS
        msg.priority = 10000
        return msg

    def get_flow_table_remove_msg(self):
        msg = of.ofp_flow_mod()
        msg.match = self.match
        msg.command = of.OFPFC_DELETE_STRICT
        return msg

    def get_average_rate(self):
        return self.running_rate_sum / Flow.RUNNING_AVERAGE_WINDOW

    def add_rate(self, new_rate):
        self.running_rate_sum += new_rate - self.bit_rates.pop(0)
        self.bit_rates.append(new_rate)

    def update_total_bytes_transferred(self, new_total):
        transmission_rate = 8 * \
            (new_total - self.total_bytes) / FLOW_STATS_INTERVAL_SECS
        self.total_bytes = new_total
        self.add_rate(transmission_rate)


class SizeBasedDynamicDmzSwitch (object):

    def __init__(self, connection, transparent, dpi_port):
        # Switch we'll be adding L2 learning switch capabilities to
        self.connection = connection
        self.transparent = transparent
        self.dpi_port = dpi_port
        self._flow_bandwidths = {}
        # Our table
        self.macToPort = {}
        self.flows = {}
        self.dmz_flows = {}

        # We want to hear PacketIn messages, so we listen
        # to the connection
        connection.addListeners(self)

        # We just use this to know when to log a helpful message
        self.hold_down_expired = _flood_delay == 0

        self._statistic()
        core.openflow.addListenerByName(
            "FlowStatsReceived", self.handle_flow_stats)

        log.debug("Started Switch.")

        threading.Thread(target=self.webserver_worker).start()

    def webserver_worker(self):
        app = Flask(__name__)

        @app.route("/")
        def hello():
            return render_template("index.html")

        @app.route("/data")
        def data():
            # convert tuples to strings and send
            return json.dumps({str(k): v for k, v in self._flow_bandwidths.iteritems()})

        app.run(host='0.0.0.0')

    def _statistic(self):
        for con in core.openflow.connections:
            con.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
        threading.Timer(FLOW_STATS_INTERVAL_SECS, self._statistic).start()

    def handle_flow_stats(self, event):
        self._dpi_port = getOpenFlowPort(self.connection, self.dpi_port)
        self._flow_bandwidths.clear()
        current_time = time.time()

        # look through all flows and look for elephant flows
        for f in event.stats:
            # Create an identification key for this flow using the send/recieve
            # ports and hardware interface
            key = (f.match.nw_src, f.match.nw_dst,
                   f.match.tp_src, f.match.tp_dst, f.match.in_port)

            current_flow = None
            if key in self.flows:
                current_flow = self.flows[key]
            elif key in self.dmz_flows:
                current_flow = self.dmz_flows[key]
            else:
                current_flow = self.flows[key] = Flow(f.match)

            current_flow.update_total_bytes_transferred(f.byte_count)
            transmission_rate_bits = current_flow.get_average_rate()

            self._flow_bandwidths[key] = transmission_rate_bits

            # Do not look for elephant flows coming from the DPI.
            if f.match.in_port == self._dpi_port:
                continue

            # If Elephant flow is detected
            if not key in self.dmz_flows and transmission_rate_bits > THRESHOLD_BITS_PER_SEC:
                self.dmz_flows[key] = current_flow
                del self.flows[key]

                if f.match.dl_dst in self.macToPort:
                    current_flow.timeout = time.time() + random.randint(RANDOM_TIMEOUT['min'], RANDOM_TIMEOUT['max']) #TODO randomize
                    self.connection.send(
                        current_flow.get_flow_table_mod_msg(self.macToPort[f.match.dl_dst]))
                else:
                    self.connection.send(
                        current_flow.get_flow_table_mod_msg(of.OFPP_FLOOD))

                log.debug("ELEPHANT FLOW REROUTED: %s->%s %s->%s, Inport: %d, Bytes: %d, Rate: %f" %
                          (current_flow.network_layer_src,
                           current_flow.network_layer_dst,
                           current_flow.transport_layer_src,
                           current_flow.transport_layer_dst,
                           current_flow.hardware_port,
                           current_flow.total_bytes,
                           transmission_rate_bits))

            #if a mouse flow was detected in the DMZ
            elif key in self.dmz_flows and transmission_rate_bits < THRESHOLD_BITS_PER_SEC:
                self.flows[key] = current_flow
                del self.dmz_flows[key]

                self.connection.send(current_flow.get_flow_table_mod_msg(self._dpi_port))
                log.debug("MOUSE FLOW REROUTED: %s->%s %s->%s, Inport: %d, Bytes: %d, Rate: %f" %
                          (current_flow.network_layer_src,
                           current_flow.network_layer_dst,
                           current_flow.transport_layer_src,
                           current_flow.transport_layer_dst,
                           current_flow.hardware_port,
                           current_flow.total_bytes,
                           transmission_rate_bits))

            #check for DMZ timeouts
            if key in self.dmz_flows and current_time >= current_flow.timeout:
                self.flows[key] = current_flow
                del self.dmz_flows[key]

                self.connection.send(current_flow.get_flow_table_mod_msg(self._dpi_port))
                log.debug("ELEPHANT FLOW KICKED: %s->%s %s->%s, Inport: %d, Bytes: %d, Rate: %f" %
                          (current_flow.network_layer_src,
                           current_flow.network_layer_dst,
                           current_flow.transport_layer_src,
                           current_flow.transport_layer_dst,
                           current_flow.hardware_port,
                           current_flow.total_bytes,
                           transmission_rate_bits))



    def _handle_PacketIn(self, event):
        packet = event.parsed

        def flood(message=None):
            """ Floods the packet """
            msg = of.ofp_packet_out()
            if time.time() - self.connection.connect_time >= _flood_delay:
                # Only flood if we've been connected for a little while...

                if self.hold_down_expired is False:
                    # Oh yes it is!
                    self.hold_down_expired = True
                    log.info("%s: Flood hold-down expired -- flooding",
                             dpid_to_str(event.dpid))

                if message is not None:
                    log.debug(message)
                #log.debug("%i: flood %s -> %s", event.dpid,packet.src,packet.dst)
                # OFPP_FLOOD is optional; on some switches you may need to change
                # this to OFPP_ALL.
                msg.actions.append(
                    of.ofp_action_output(port=of.OFPP_FLOOD))
            else:
                pass
                #log.info("Holding down flood for %s", dpid_to_str(event.dpid))
            msg.data = event.ofp
            msg.in_port = event.port
            self.connection.send(msg)

        def drop(duration=None):
            """
            Drops this packet and optionally installs a flow to continue
            dropping similar ones for a while
            """
            log.debug("Dropping packet")
            if duration is not None:
                if not isinstance(duration, tuple):
                    duration = (duration, duration)
                    msg = of.ofp_flow_mod()
                    msg.match = of.ofp_match.from_packet(packet)
                    msg.idle_timeout = duration[0]
                    msg.hard_timeout = duration[1]
                    msg.buffer_id = event.ofp.buffer_id
                    self.connection.send(msg)
                elif event.ofp.buffer_id is not None:
                    msg = of.ofp_packet_out()
                    msg.buffer_id = event.ofp.buffer_id
                    msg.in_port = event.port
                    self.connection.send(msg)


        self._dpi_port = getOpenFlowPort(self.connection, self.dpi_port)

        if not packet.dst.is_multicast and event.port != self._dpi_port:
            self.macToPort[packet.src] = event.port
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, event.port)
            msg.idle_timeout = FLOW_ENTRY_IDLE_TIMEOUT_SECS
            msg.hard_timeout = FLOW_ENTRY_HARD_TIMEOUT_SECS
            msg.actions.append(of.ofp_action_output(port=self._dpi_port))
            msg.data = event.ofp
            self.connection.send(msg)
            #log.debug("Create Flow Table Entry: %s:%s -> %s:%s, ingress interface: %s" %
            #          (msg.match.nw_src, msg.match.tp_src, msg.match.nw_dst, msg.match.tp_dst, event.port))
            return

        if not self.transparent:
            if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
                drop()
                return

        if packet.dst.is_multicast:
            flood()
        else:
            if packet.dst not in self.macToPort:
                flood("Port for %s unknown -- flooding" % (packet.dst,))
            else:
                port = self.macToPort[packet.dst]
                if port == event.port:
                    log.warning("Same port for packet from %s -> %s on %s.%s.  Drop." %
                                (packet.src, packet.dst, dpid_to_str(event.dpid), port))
                    return

                msg = of.ofp_flow_mod()
                msg.match = of.ofp_match.from_packet(packet, event.port)
                msg.idle_timeout = FLOW_ENTRY_IDLE_TIMEOUT_SECS
                msg.hard_timeout = FLOW_ENTRY_HARD_TIMEOUT_SECS
                msg.actions.append(of.ofp_action_output(port=port))
                msg.data = event.ofp
                self.connection.send(msg)
                #log.debug("Create Flow Table Entry: %s:%s -> %s:%s, ingress interface: %s" %
                #          (msg.match.nw_src, msg.match.tp_src, msg.match.nw_dst, msg.match.tp_dst, event.port))


class l2_learning (object):
    """
    Waits for OpenFlow switches to connect and makes them learning switches.
    """

    def __init__(self, transparent, dpi_port):
        core.openflow.addListeners(self)
        self.transparent = transparent
        self.dpi_port = dpi_port

    def _handle_ConnectionUp(self, event):
        log.debug("Connection %s" % (event.connection,))
        SizeBasedDynamicDmzSwitch(
            event.connection, self.transparent, self.dpi_port)


def launch(transparent=False, hold_down=_flood_delay, dpi_port='eth0'):
    """
    Starts an L2 learning switch.
    """
    try:
        global _flood_delay
        _flood_delay = int(str(hold_down), 10)
        assert _flood_delay >= 0
    except:
        raise RuntimeError("Expected hold-down to be a number")

    core.registerNew(l2_learning, str_to_bool(transparent), dpi_port)
