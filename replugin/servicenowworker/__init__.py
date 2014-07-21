# -*- coding: utf-8 -*-
# Copyright © 2014 SEE AUTHORS FILE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
ServiceNow worker.
"""
import os
import requests

from urllib import quote_plus

from reworker.worker import Worker


class ServiceNowWorkerError(Exception):
    """
    Base exception class for ServiceNowWorker errors.
    """
    pass


class ServiceNowWorker(Worker):
    """
    Worker which provides basic functionality with ServiceNow change records.
    """

    #: All allowed subcommands
    subcommands = ('DoesChangeRecordExist', )

    def does_change_record_exist(self, body, output):
        """
        Subcommand which checks to see if a change record exists.

        *Parameters Requires*:
            * change_record: the record to look for.
        """
        expected_record = body['parameters'].get('change_record', None)
        if not expected_record:
            raise ServiceNowWorkerError(
                'No change_record to search for given.')

        output.info('Checking for change record %s ...' % expected_record)

        # Service now call
        url = self._config['api_root_url'] + '/table/change_request'
        url += '?sysparm_query=%s&sysparm_fields=number&sysparm_limit=2' % (
            quote_plus('number=' + expected_record))

        response = requests.get(
            url,
            auth=(
                self._config['servicenow_user'],
                self._config['servicenow_password']),
            headers={'Accept': 'application/json'})

        # We should get a 200, else it doesn't exist or server issue
        if response.status_code == 200:
            change_record = response.json()['result'][0]['number']
            if change_record == expected_record:
                output.info('Found change record %s' % change_record)
                return {'status': 'completed', 'data': {'exists': True}}
        # 404 means it can't be found
        elif response.status_code == 404:
            output.info('Change record %s does not exist.' % expected_record)
            return {'status': 'completed', 'data': {'exists': False}}
        # Anything else is an error
        raise ServiceNowWorkerError('API returned %s instead of 200' % (
            response.status_code))

    def process(self, channel, basic_deliver, properties, body, output):
        """
        Writes out output messages from the bus.

        *Keys Requires*:
            * subcommand: the subcommand to execute.
        """
        # Ack the original message
        self.ack(basic_deliver)
        corr_id = str(properties.correlation_id)

        try:
            try:
                subcommand = str(body['parameters']['subcommand'])
                if subcommand not in self.subcommands:
                    raise KeyError()
            except KeyError:
                raise ServiceNowWorkerError(
                    'No valid subcommand given. Nothing to do!')

            if subcommand == 'DoesChangeRecordExist':
                self.app_logger.info(
                    'Executing subcommand %s for correlation_id %s' % (
                        subcommand, corr_id))
                result = self.does_change_record_exist(body, output)
            else:
                self.app_logger.warn(
                    'Could not the implementation of subcommand %s' % (
                        subcommand))
                raise ServiceNowWorkerError('No subcommand implementation')

            # Send results back
            self.send(
                properties.reply_to,
                corr_id,
                result,
                exchange=''
            )

            # Notify on result. Not required but nice to do.
            self.notify(
                'ServiceNowWorker Executed Successfully',
                'ServiceNowWorker successfully executed %s. See logs.' % (
                    subcommand),
                'completed',
                corr_id)

            # Send out responses
            self.app_logger.info(
                'ServiceNowWorker successfully executed %s for '
                'correlation_id %s. See logs.' % (
                    subcommand, corr_id))

        except ServiceNowWorkerError, fwe:
            # If a ServiceNowWorkerError happens send a failure log it.
            self.app_logger.error('Failure: %s' % fwe)
            self.send(
                properties.reply_to,
                corr_id,
                {'status': 'failed'},
                exchange=''
            )
            self.notify(
                'ServiceNowWorker Failed',
                str(fwe),
                'failed',
                corr_id)
            output.error(str(fwe))


def main():  # pragma: no cover
    from reworker.worker import runner
    runner(ServiceNowWorker)


if __name__ == '__main__':  # pragma nocover
    main()
