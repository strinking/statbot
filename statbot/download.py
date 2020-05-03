#
# __init__.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import logging
from io import BytesIO
from ssl import SSLError

import aiohttp

logger = logging.getLogger(__name__)

# Maximum size to download from foreign sites
MAXIMUM_FILE_SIZE = 24 * 1024 * 1024

# How large each read request should be
CHUNK_SIZE = 4 * 1024

# Prevent connections from hanging for too long
TIMEOUT = aiohttp.ClientTimeout(total=45, sock_read=5)


async def download_link(url):
    async with aiohttp.ClientSession(timeout=TIMEOUT, trust_env=True) as session:
        return await download(session, url)


async def download(session, url):
    binio = BytesIO()
    try:
        async with session.get(url) as response:
            if response.content_length is not None:
                if response.content_length > MAXIMUM_FILE_SIZE:
                    logger.info(
                        "File is reportedly too large (%d bytes > %d bytes)",
                        response.content_length,
                        MAXIMUM_FILE_SIZE,
                    )
                    return None

            while len(binio.getbuffer()) < MAXIMUM_FILE_SIZE:
                chunk = await response.content.read(CHUNK_SIZE)
                if chunk:
                    binio.write(chunk)
                else:
                    return binio
            logger.info(
                "File was too large, bailing out (max file size: %d bytes)",
                MAXIMUM_FILE_SIZE,
            )
            return None
    except SSLError:
        # Ignore SSL errors
        pass
    except Exception as error:
        logger.info("Error while downloading %s for hash check", url, exc_info=error)
        return None
