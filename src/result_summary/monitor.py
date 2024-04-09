# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (C) 2024 Collabora Limited
# Author: Ricardo Cañuelo Navarro <ricardo.canuelo@collabora.com>
#
# monitor-mode-specifc code for result-summary.

from datetime import datetime, timezone
import os
import re

import result_summary


def setup(service, args, context):
    base_filter = context['preset_params'][0]
    sub_id = service._api_helper.subscribe_filters({
        'kind': base_filter['kind'],
        'state': base_filter['state'],
    })
    if not sub_id:
        raise Exception("Error subscribing to event")
    return {'sub_id': sub_id}


def stop(service, context):
    if context and context.get('sub_id'):
        service._api_helper.unsubscribe_filters(context['sub_id'])


def get_item(dict, item, default=None):
    """General form of dict.get() that supports the retrieval of
    dot-separated fields in nested dicts.
    """
    if not dict:
        return default
    items = item.split('.')
    if len(items) == 1:
        return dict.get(items[0], default)
    return get_item(dict.get(items[0], default), '.'.join(items[1:]), default)


def filter_node(node, params):
    """Returns True if <node> matches the constraints defined in
    the <params> dict, where each param is defined like:

        node_field : value

    with an optional operator (ne, gt, lt, re):

        node_field__op : value

    The value matching is done differently depending on the
    operator (equal, not equal, greater than, lesser than,
    regex)

    If the node doesn't match the full set of parameter
    constraints, it returns False.
    """
    for param_name, value in params.items():
        field, _, cmd = param_name.partition('__')
        node_value = get_item(node, field)
        if cmd == 'ne':
            if node_value == value:
                return False
        elif cmd == 'gt':
            if node_value <= value:
                return False
        elif cmd == 'lt':
            if node_value >= value:
                return False
        elif cmd == 're':
            if not re.search(value, node_value):
                return False
        else:
            if node_value != value:
                return False
    return True


def run(service, context):
    while True:
        node = service._api_helper.receive_event_node(context['sub_id'])
        preset_params = context['preset_params']
        for param_set in context['preset_params']:
            if filter_node(node, {**param_set, **context['extra_query_params']}):
                service.log.info(f"Result received: {node['id']}")
                template_params = {
                    'metadata': context['metadata'],
                    'node': node,
                }
                output_text = context['template'].render(template_params)
                output = context['output']
                if not output:
                    # Since we expect many reports to be generated,
                    # prepend them with a timestamp
                    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                    if 'output' in context['metadata']:
                        output = now_str + '__' + context['metadata']['output']
                if output:
                    with open(os.path.join(result_summary.OUTPUT_DIR, output), 'w') as output_file:
                        output_file.write(output_text)
                    service.log.info(f"Report generated in {output}")
                else:
                    result_summary.logger.info(output_text)
            else:
                service.log.debug(f"Result received but filtered: {node['id']}")
    return True
