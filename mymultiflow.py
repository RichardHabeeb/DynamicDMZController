
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

from utils import *
import time
import datetime
import threading


#-------------------------------------------------------------------------
# CONSTANTS
#-------------------------------------------------------------------------
FLOW_STATS_INTERVAL_SECS = 2
THRESHOLD_IN_KBPS = 50000 / 8
FLOW_ENTRY_IDLE_TIMEOUT_SECS = 10
FLOW_ENTRY_HARD_TIMEOUT_SECS = 800

#-------------------------------------------------------------------------
# VARIABLES
#-------------------------------------------------------------------------

log = core.getLogger()
# We don't want to flood immediately when a switch connects.
# Can be overriden on commandline.
_flood_delay = 0





class SizeBasedDynamicDmzSwitch (object):

    def __init__(self, connection, transparent, dpi_port):
        # Switch we'll be adding L2 learning switch capabilities to
        self.connection = connection
        self.transparent = transparent
        self.dpi_port = dpi_port
        self._flowstats = {}
        self._flow_bandwidths = {}
        # Our table
        self.macToPort = {}



        # We want to hear PacketIn messages, so we listen
        # to the connection
        connection.addListeners(self)

        # We just use this to know when to log a helpful message
        self.hold_down_expired = _flood_delay == 0

        self._statistic()
        core.openflow.addListenerByName(
            "FlowStatsReceived", self.handle_flow_stats)
        # log.debug("Initializing SizeBasedDynamicDmzSwitch, transparent=%s",
        #          str(self.transparent))

        log.debug("Started Switch.")

        threading.Thread(target=self.webserver_worker).start()

    def webserver_worker(self):
        app = Flask(__name__)

        @app.route("/")
        def hello():
            return render_template("index.html")

        @app.route("/data")
        def data():
            #convert tuples to strings and send
            return json.dumps({str(k): v for k, v in self._flow_bandwidths.iteritems()})

        app.run(host='0.0.0.0')

    def _statistic(self):
        print datetime.datetime.now()
        for con in core.openflow.connections:
            con.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
        threading.Timer(FLOW_STATS_INTERVAL_SECS, self._statistic).start()

    def handle_flow_stats(self, event):
        self._dpi_port = getOpenFlowPort(self.connection, self.dpi_port)
        self._cur_flow = {}
        self._flow_bandwidths.clear()

        # look through all flows and look for elephant flows
        for f in event.stats:
            log.debug("Source: %s->%s %s->%s, Inport: %d, Bytes: %d" % (f.match.nw_src,
                                                                        f.match.nw_dst,
                                                                        f.match.tp_src,
                                                                        f.match.tp_dst,
                                                                        f.match.in_port,
                                                                        f.byte_count))


            # Create an identification key for this flow using the send/recieve
            # ports and
            key = (f.match.nw_src, f.match.nw_dst,
                   f.match.tp_src, f.match.tp_dst, f.match.in_port)

            # Store number of bytes transmitted by the flow in total.
            self._cur_flow[key] = f.byte_count

            # Compute the transmission_rate
            transmission_rate_mbps = 0
            if(key in self._flowstats and self._cur_flow[key] >= self._flowstats[key]):
                transmission_rate_mbps = (self._cur_flow[key] - self._flowstats[key]) / FLOW_STATS_INTERVAL_SECS
            else:
                transmission_rate_mbps = self._cur_flow[key] / FLOW_STATS_INTERVAL_SECS

            self._flow_bandwidths[key] = transmission_rate_mbps

            # Do not look for elephant flows coming from the DPI.
            if f.match.in_port == self._dpi_port:
                continue

            # If Elephant flow is detected
            if transmission_rate_mbps > THRESHOLD_IN_KBPS * 1024:

                msg = of.ofp_flow_mod()
                msg.match = f.match
                msg.idle_timeout = FLOW_ENTRY_IDLE_TIMEOUT_SECS
                msg.hard_timeout = FLOW_ENTRY_HARD_TIMEOUT_SECS
                msg.priority = 10000
                if f.match.dl_dst in self.macToPort:
                    msg.actions.append(of.ofp_action_output(
                        port=self.macToPort[f.match.dl_dst]))
                    log.debug("ELEPHANT FLOW REROUTED!")
                else:
                    msg.actions.append(
                        of.ofp_action_output(port=of.OFPP_FLOOD))

                msg.command = of.OFPFC_MODIFY
                self.connection.send(msg)

        self._flowstats = self._cur_flow

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
                    log.debug("FLOW MODIFYING... DROPING FLOWS")

        self._dpi_port = getOpenFlowPort(self.connection, self.dpi_port)

        if event.port != self._dpi_port:
            self.macToPort[packet.src] = event.port
            log.debug("Redirecting to DPI for %s.%i -> %s" %
                      (packet.src, event.port, packet.dst))
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, event.port)
            msg.idle_timeout = FLOW_ENTRY_IDLE_TIMEOUT_SECS
            msg.hard_timeout = FLOW_ENTRY_HARD_TIMEOUT_SECS
            msg.actions.append(of.ofp_action_output(port=self._dpi_port))
            msg.data = event.ofp
            self.connection.send(msg)
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

                log.debug("installing flow for %s.%i -> %s.%i" %
                          (packet.src, event.port, packet.dst, port))
                msg = of.ofp_flow_mod()
                msg.match = of.ofp_match.from_packet(packet, event.port)
                msg.idle_timeout = FLOW_ENTRY_IDLE_TIMEOUT_SECS
                msg.hard_timeout = FLOW_ENTRY_HARD_TIMEOUT_SECS
                msg.actions.append(of.ofp_action_output(port=port))
                msg.data = event.ofp
                self.connection.send(msg)


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
        SizeBasedDynamicDmzSwitch(event.connection, self.transparent, self.dpi_port)


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
