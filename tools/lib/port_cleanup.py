#!/usr/bin/env python3
#
# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
A tool to delete neutron ports which match a port name regex
and/or port status.
"""

import argparse
import logging
import re
import sys
import time

from common.tools_common import get_openstack_clients

DESCRIPTION = sys.modules[__name__].__doc__

# Usage example:
# ./port-cleanup -pn "juju-osci-.*-machine.*ext-port" -ps "DOWN" --delete


def validate_config(conf):
    """Check config and return openstack clients if successful."""
    return get_openstack_clients()


def get_servers_in_state(clients, status=None):
    """Get a list of nova servers (instances) which are in a specific state.
    """

    if status is None:
        status = 'ERROR'

    _servers = []
    for instance in clients['nv'].servers.list():
        if instance.status == status:
            _servers.append(instance)
    logging.info('Nova servers in {} status: {}'.format(status, len(_servers)))
    return _servers


def get_ports(clients, name_regex=None, status=None):
    """Get a list of neutron ports, or a subset of ports which match
    a pattern by name.
    """

    if not name_regex:
        name_regex = ""
    re_name = re.compile(name_regex)

    ports = clients['nu'].list_ports()['ports']
    logging.info('Neutron ports total: {}'.format(len(ports)))

    _ports_matched = []
    for port in ports:
        if ((re_name.match(port['name']) and not status) or
                (re_name.match(port['name']) and status and
                    port['status'] == status)):
            _ports_matched.append(port)

    logging.info('Neutron ports matched: {}'.format(len(_ports_matched)))
    return _ports_matched


def delete_port(clients, port_id):
    """Delete a neutron port based on the port ID value.
    """
    # TODO: Add exception handling
    clients['nu'].delete_port(port_id)


def do_cleanup(conf, clients):
    """Perform neutron port cleanup.
    """
    # juju-osci-.*-machine.*ext-port
    matching_ports = get_ports(clients,
                               name_regex=conf['port_name_regex'],
                               status=conf['port_status'])

    # Destructive
    if conf['port_delete'] is True and matching_ports:
        # Provide last ditch opportunity for user to bail.
        logging.info('Deleting ports after 10s delay.')
        time.sleep(10)
        for port in matching_ports:
            if not conf['quiet']:
                logging.info('Deleting port: {}  {}  {}'.format(
                    port['id'], port['name'], port['status']))
            delete_port(clients, port_id=port['id'])

    # Announce Only
    elif conf['port_delete'] is not True and matching_ports:
        for port in matching_ports:
            if not conf['quiet']:
                logging.info('Not deleting port: {}  {}  {}'.format(
                    port['id'], port['name'], port['status']))

    # TODO: The following are for a separate tool, split out of here later.
    active_servers = get_servers_in_state(clients, status="ACTIVE")
    error_servers = get_servers_in_state(clients, status="ERROR")
    logging.debug('Active nova servers: {}'.format(active_servers))
    logging.debug('Error nova servers: {}'.format(error_servers))

    return 0


def cli_args():
    """Command line arguments"""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('-pn', '--port-name-regex',
                        dest='port_name_regex', action='store',
                        help='Regex string to use to match port names')

    parser.add_argument('-ps', '--port-status',
                        dest='port_status', action='store',
                        help='Status of port to match (exact string)')

    parser.add_argument('-v', '--debug',
                        help='Enable verbose debug output',
                        action='store_true', required=False)

    parser.add_argument('-q', '--quiet',
                        help='Slightly less verbose, but not silent',
                        action='store_true', required=False)

    parser.add_argument('--delete',
                        dest='port_delete',
                        help='Delete matching ports (USE WITH CAUTION)',
                        action='store_true', required=False)

    options = parser.parse_args()
    return options


def set_debug(conf):
    """Set debug."""
    if conf['debug']:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level)


if __name__ == '__main__':
    conf = vars(cli_args())
    set_debug(conf)
    logging.info('Command arguments: {}'.format(conf))
    clients = validate_config(conf)
    sys.exit(do_cleanup(conf, clients))
