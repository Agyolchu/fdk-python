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
import io

from fdk import constants
from fdk import log
from fdk import response


async def process_chunk(connection: h11.Connection,
                        request_reader: asyncio.StreamReader):
    """
    Reads the request in chunks until can parse
    the request successfully
    :param connection: h11 request parser
    :type connection: h11.Connection
    :param request_reader: async stream reader
    :type request_reader: asyncio.StreamReader
    :return: request and body
    :rtype tuple
    """
    # TODO(denismakogon): replace io.BytesIO with asyncio.StreamReader
    # this change will be required when an FDK will enforce customer's
    # function to be a coroutine
    request, body = None, io.BytesIO()
    log.log("starting process_chunk")
    while True:
        log.log("process_chunk: reading chunk of data from async reader")
        buf = await request_reader.read(constants.ASYNC_IO_READ_BUFFER)
        log.log("process_chunk: buffer filled")
        connection.receive_data(buf)
        log.log("process_chunk: sending data to h11")
        while True:
            event = connection.next_event()
            log.log("process_chunk: event type {0}"
                    .format(type(event)))
            if isinstance(event, h11.Request):
                request = event
            if isinstance(event, h11.Data):
                body.write(event.data)
            if isinstance(event, h11.EndOfMessage):
                return request, body
            if isinstance(event, (h11.NEED_DATA, h11.PAUSED)):
                log.log("requiring more data or connection paused")
                break
            if isinstance(event, h11.ConnectionClosed):
                raise Exception("connection closed")


async def read_request(connection, request_reader):
    """
    Request processor wrapper
    :param connection: h11 request parser
    :type connection: h11.Connection
    :param request_reader: async stream reader
    :type request_reader: asyncio.StreamReader
    :return:
    """
    while True:
        request, body = await process_chunk(connection, request_reader)
        if request is None:
            raise Exception("unable to read incoming request")
        return request, body


async def write_response(
        connection: h11.Connection,
        func_response: response.Response,
        response_writer: asyncio.StreamWriter):
    """
    Processes function's response
    :param connection: h11 request parser
    :type connection: h11.Connection
    :param func_response: function's response
    :type func_response: fdk.response.Response
    :param response_writer: async stream writer
    :type response_writer: asyncio.StreamWriter
    :return: None
    """
    headers = func_response.ctx.GetResponseHeaders()
    status = func_response.status()
    log.log("response headers: {}".format(headers))
    log.log("response status: {}".format(status))
    resp_data = str(func_response.body()).encode("utf-8")
    headers.update({constants.CONTENT_LENGTH: str(len(resp_data))})

    response_writer.write(
        connection.send(h11.Response(
            status_code=status, headers=headers.items())
        )
    )
    response_writer.write(connection.send(
        h11.Data(
            data=resp_data))
    )
    response_writer.write(connection.send(h11.EndOfMessage()))


async def write_error(ex: Exception,
                      connection: h11.Connection,
                      response_writer: asyncio.StreamWriter):
    """
    Turns an exception into an error
    :param ex: an exception
    :type ex: Exception
    :param connection: h11 request parser
    :type connection: h11.Connection
    :param response_writer: async stream writer
    :type response_writer: asyncio.StreamWriter
    :return: None
    """
    data = str(ex)
    headers = {
        constants.CONTENT_TYPE: "text/plain",
        constants.CONTENT_LENGTH: str(len(data))
    }
    response_writer.write(
        connection.send(h11.Response(
            status_code=502, headers=headers.items())
        )
    )

    response_writer.write(connection.send(
        h11.Data(
            data=data.encode("utf-8")))
    )
    response_writer.write(connection.send(h11.EndOfMessage()))
