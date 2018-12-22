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
import os
import sys

from fdk import constants
from fdk import customer_code
from fdk import log
from fdk.http import routine
from fdk.http import event_handler

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    log.log("uvloop is not installed, using default event loop")


async def create_unix_server(client_connected_cb, path=None, *,
                             loop=None,
                             limit=constants.ASYNC_IO_READ_BUFFER,
                             start_serving=False):
    if loop is None:
        loop = asyncio.get_event_loop()

    return await loop.create_unix_server(
        routine.protocol_factory(client_connected_cb, loop, limit=limit),
        path, start_serving=start_serving)


def start(handle_code: customer_code.Function,
          uds: str,
          loop: asyncio.AbstractEventLoop=None):
    """
    Unix domain socket HTTP server entry point
    :param handle_code: customer's code
    :type handle_code: fdk.customer_code.Function
    :param uds: path to a Unix domain socket
    :type uds: str
    :param loop: event loop
    :type loop: asyncio.AbstractEventLoop
    :return: None
    """
    log.log("in http_stream.start")
    socket_path = os.path.normpath(str(uds).lstrip("unix:"))
    socket_dir, socket_file = os.path.split(socket_path)
    if socket_file == "":
        sys.exit("malformed FN_LISTENER env var "
                 "value: {0}".format(socket_path))

    phony_socket_path = os.path.join(
        socket_dir, "phony" + socket_file)

    log.log("deleting socket files if they exist")
    try:
        os.remove(socket_path)
        os.remove(phony_socket_path)
    except OSError:
        pass

    log.log("starting unix socket site")
    unix_srv = loop.run_until_complete(
        create_unix_server(
            event_handler.event_handle(handle_code),
            path=phony_socket_path,
            loop=loop, limit=constants.ASYNC_IO_READ_BUFFER,
            start_serving=False,
        )
    )
    try:
        log.log("CHMOD 666 {0}".format(phony_socket_path))
        os.chmod(phony_socket_path, 0o666)
        log.log("phony socket permissions: {0}"
                .format(oct(os.stat(phony_socket_path).st_mode)))
        log.log("sym-linking {0} to {1}".format(
            socket_path, phony_socket_path))
        os.symlink(os.path.basename(phony_socket_path), socket_path)
        log.log("socket permissions: {0}"
                .format(oct(os.stat(socket_path).st_mode)))
        log.log("starting infinite loop")

        loop.run_until_complete(unix_srv.serve_forever())
    except (Exception, BaseException) as ex:
        log.log(str(ex))
        raise ex
    finally:
        if hasattr(loop, 'shutdown_asyncgens'):
            loop.run_until_complete(loop.shutdown_asyncgens())
        unix_srv.close()
        loop.run_until_complete(unix_srv.wait_closed())
        loop.close()


def handle(handle_code: customer_code.Function):
    """
    FDK entry point
    :param handle_code: customer's code
    :type handle_code: fdk.customer_code.Function
    :return: None
    """
    log.log("entering handle")
    if not isinstance(handle_code, customer_code.Function):
        sys.exit(
            '\n\n\nWARNING!\n\n'
            'Your code is not compatible the the latest FDK!\n\n'
            'Update Dockerfile entry point to:\n'
            'ENTRYPOINT["/python/bin/fdk", "<path-to-your-func.py>", {0}]\n\n'
            'if __name__ == "__main__":\n\tfdk.handle(handler)\n\n'
            'syntax no longer supported!\n'
            'Update your code as soon as possible!'
            '\n\n\n'.format(handle_code.__name__))

    loop = asyncio.get_event_loop()

    format_def = os.environ.get(constants.FN_FORMAT)
    lsnr = os.environ.get(constants.FN_LISTENER)
    log.log("{0} is set, value: {1}".
            format(constants.FN_FORMAT, format_def))

    if lsnr is None:
        sys.exit("{0} is not set".format(constants.FN_LISTENER))

    log.log("{0} is set, value: {1}".
            format(constants.FN_LISTENER, lsnr))

    if format_def == constants.HTTPSTREAM:
        start(handle_code, lsnr, loop=loop)
    else:
        sys.exit("incompatible function format!")
