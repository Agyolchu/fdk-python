# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import asyncio
import h11

from fdk import constants
from fdk.http import event_handler


if __name__ == "__main__":
    from fdk import fixtures

    async def hello(ctx, data=None):
        return "hello"

    connection = h11.Connection(h11.SERVER)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        asyncio.start_server(
            event_handler.event_handle(
                connection, fixtures.code(hello)),
            host="localhost", port=5000,
            limit=constants.IO_LIMIT, loop=loop)
    )
    loop.run_forever()
