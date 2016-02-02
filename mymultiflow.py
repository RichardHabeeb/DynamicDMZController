# Copyright 2011-2012 James McCauley
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An L2 learning switch.

It is derived from one written live for an SDN crash course.
It is somwhat similar to NOX's pyswitch in that it installs
exact-match rules for each flow.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow import *
from pox.lib.addresses import *
from pox.lib.util import dpid_to_str
from pox.lib.util import str_to_bool
from utils import *
import time
import datetime
import threading

log = core.getLogger()

# We don't want to flood immediately when a switch connects.
# Can be overriden on commandline.
_flood_delay = 0
FLOW_STATS_INTERVAL=2
THRESHOLD_IN_KBPS = 50000/8 #KBytes per second

class LearningSwitch (object):
  """
  The learning switch "brain" associated with a single OpenFlow switch.

  When we see a packet, we'd like to output it on a port which will
  eventually lead to the destination.  To accomplish this, we build a
  table that maps addresses to ports.

  We populate the table by observing traffic.  When we see a packet
  from some source coming from some port, we know that source is out
  that port.

  When we want to forward traffic, we look up the desintation in our
  table.  If we don't know the port, we simply send the message out
  all ports except the one it came in on.  (In the presence of loops,
  this is bad!).

  In short, our algorithm looks like this:

  For each packet from the switch:
  1) Use source address and switch port to update address/port table
  2) Is transparent = False and either Ethertype is LLDP or the packet's
     destination address is a Bridge Filtered address?
     Yes:
        2a) Drop packet -- don't forward link-local traffic (LLDP, 802.1x)
            DONE
  3) Is destination multicast?
     Yes:
        3a) Flood the packet
            DONE
  4) Port for destination address in our address/port table?
     No:
        4a) Flood the packet
            DONE
  5) Is output port the same as input port?
     Yes:
        5a) Drop packet and similar ones for a while
  6) Install flow table entry in the switch so that this
     flow goes out the appopriate port
     6a) Send the packet out appropriate port
  """
  def __init__ (self, connection, transparent, dpi_port):
    # Switch we'll be adding L2 learning switch capabilities to
    self.connection = connection
    self.transparent = transparent
    self.dpi_port = dpi_port
    self._flowstats={}
    # Our table
    self.macToPort = {}

    # We want to hear PacketIn messages, so we listen
    # to the connection
    connection.addListeners(self)

    # We just use this to know when to log a helpful message
    self.hold_down_expired = _flood_delay == 0
    
    self._statistic()
    core.openflow.addListenerByName("FlowStatsReceived", self.handle_flow_stats)
    #log.debug("Initializing LearningSwitch, transparent=%s",
    #          str(self.transparent))
   

  def _statistic(self):
    print datetime.datetime.now()
    for con in core.openflow.connections:
      con.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
    threading.Timer(FLOW_STATS_INTERVAL, self._statistic).start()
  
  def handle_flow_stats(self, event):
    self._dpi_port = getOpenFlowPort(self.connection, self.dpi_port)
    for f in event.stats:
      log.debug("Source: %s->%s %s->%s Flow: %d" % (f.match.nw_src, f.match.nw_dst, f.match.tp_src, f.match.tp_dst, f.byte_count))
    self._cur_flow={}
    for f in event.stats:
      if f.match.in_port == self._dpi_port:
        continue
      key = (f.match.nw_src,f.match.nw_dst,f.match.tp_src,f.match.tp_dst)
      if (key in self._cur_flow):
        self._cur_flow[key] = self._cur_flow[key] + f.byte_count
      else:
        self._cur_flow[key] = f.byte_count
      if (key in self._flowstats and ((self._cur_flow[key]-self._flowstats[key])/FLOW_STATS_INTERVAL>THRESHOLD_IN_KBPS*1024 or (self._cur_flow[key]<self._flowstats[key] and self._cur_flow[key]/FLOW_STATS_INTERVAL>THRESHOLD_IN_KBPS*1024))) or ((key not in self._flowstats) and (self._cur_flow[key]/FLOW_STATS_INTERVAL>THRESHOLD_IN_KBPS*1024)): #If Elephant flow is detected
        if (key in self._flowstats and ((self._cur_flow[key]-self._flowstats[key])/FLOW_STATS_INTERVAL>THRESHOLD_IN_KBPS*1024)):
          print 111111111111111111111111111111
        elif (key in self._flowstats and  (self._cur_flow[key]<self._flowstats[key] and self._cur_flow[key]/FLOW_STATS_INTERVAL>THRESHOLD_IN_KBPS*1024)):
          print "_cur_flow", self._cur_flow[key]
          print "_flowstats",self._flowstats[key] 
        elif ((key not in self._flowstats) and (self._cur_flow[key]/FLOW_STATS_INTERVAL>THRESHOLD_IN_KBPS*1024)):
          print 333333333333333333333333333333
        msg = of.ofp_flow_mod()
        #msg.match=of.ofp_match()
        #msg.match.dl_src = f.match.dl_src
        #msg.match.dl_dst = f.match.dl_dst
        #msg.match.nw_src = f.match.nw_src
        #msg.match.nw_dst = f.match.nw_dst
        #msg.match.tp_src = f.match.tp_src
        #msg.match.tp_dst = f.match.tp_dst
        msg.match = f.match
        msg.idle_timeout = 10
        msg.hard_timeout = 800
        msg.priority = 10000
        if f.match.dl_dst in self.macToPort:
          msg.actions.append(of.ofp_action_output(port = self.macToPort[f.match.dl_dst]))
          log.debug("ELEPHANT FLOW REROUTED!")
        else:
          msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
        #msg.match.in_port = self._dpi_port
        #log.debug(msg.match)
        #msg.command = of.OFPFC_DELETE
        #self.connection.send(msg)
        msg.command = of.OFPFC_MODIFY
        #msg.match.wildcards = msg.match.wildcards | 0x01
        log.debug(msg.match)
        self.connection.send(msg)
        log.debug(msg)
    self._flowstats=self._cur_flow
    
 
  def _handle_PacketIn (self, event):
    """
    Handle packet in messages from the switch to implement above algorithm.
    """
    packet = event.parsed

    def flood (message = None):
      """ Floods the packet """
      msg = of.ofp_packet_out()
      if time.time() - self.connection.connect_time >= _flood_delay:
        # Only flood if we've been connected for a little while...

        if self.hold_down_expired is False:
          # Oh yes it is!
          self.hold_down_expired = True
          log.info("%s: Flood hold-down expired -- flooding",
              dpid_to_str(event.dpid))

        if message is not None: log.debug(message)
        #log.debug("%i: flood %s -> %s", event.dpid,packet.src,packet.dst)
        # OFPP_FLOOD is optional; on some switches you may need to change
        # this to OFPP_ALL.
        msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
      else:
        pass
        #log.info("Holding down flood for %s", dpid_to_str(event.dpid))
      msg.data = event.ofp
      msg.in_port = event.port
      self.connection.send(msg)

    def drop (duration = None):
      """
      Drops this packet and optionally installs a flow to continue
      dropping similar ones for a while
      """
      if duration is not None:
        if not isinstance(duration, tuple):
          duration = (duration,duration)
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
      log.debug ("FLOW MODIFYING... DROPING FLOWS")

    self._dpi_port = getOpenFlowPort(self.connection, self.dpi_port)
      
    if event.port != self._dpi_port:
      self.macToPort[packet.src] = event.port # 1
    if event.port != self._dpi_port:
        log.debug("Redirecting to DPI for %s.%i -> %s" %
                  (packet.src, event.port, packet.dst))
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.idle_timeout = 10
        msg.hard_timeout = 800
        msg.actions.append(of.ofp_action_output(port = self._dpi_port))
        msg.data = event.ofp 
        self.connection.send(msg)
        return

    if not self.transparent: # 2
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        drop() # 2a
        return

    if packet.dst.is_multicast:
      flood() # 3a
    else:
      if packet.dst not in self.macToPort: # 4
        flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
      else:
        port = self.macToPort[packet.dst]
        if port == event.port: # 5
          # 5a
          log.warning("Same port for packet from %s -> %s on %s.%s.  Drop."
              % (packet.src, packet.dst, dpid_to_str(event.dpid), port))
          #drop(10)
          return
        # 6
        log.debug("installing flow for %s.%i -> %s.%i" %
                  (packet.src, event.port, packet.dst, port))
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.idle_timeout = 10
        msg.hard_timeout = 800
        msg.actions.append(of.ofp_action_output(port = port))
        msg.data = event.ofp # 6a
        self.connection.send(msg)


class l2_learning (object):
  """
  Waits for OpenFlow switches to connect and makes them learning switches.
  """
  def __init__ (self, transparent, dpi_port):
    core.openflow.addListeners(self)
    self.transparent = transparent
    self.dpi_port = dpi_port

  def _handle_ConnectionUp (self, event):
    log.debug("Connection %s" % (event.connection,))
    LearningSwitch(event.connection, self.transparent, self.dpi_port)


def launch (transparent=False, hold_down=_flood_delay, dpi_port='eth0'):
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
