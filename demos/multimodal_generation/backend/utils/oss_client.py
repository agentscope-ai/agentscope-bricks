# -*- coding: utf-8 -*-
import os
from typing import Optional

import oss2


class OssClient:

    def __init__(
        self,
        endpoint: Optional[str] = None,
        bucket: Optional[str] = None,
        directory: Optional[str] = None,
    ) -> None:
        ak = os.environ.get("OSS_ACCESS_KEY_ID")
        sk = os.environ.get("OSS_ACCESS_KEY_SECRET")
        if not ak or not sk:
            raise ValueError("oss ak or sk is not set")

        if not endpoint:
            endpoint = os.environ.get("OSS_ENDPOINT")

        if not bucket:
            bucket = os.environ.get("OSS_BUCKET")

        if not directory:
            directory = os.environ.get("OSS_DIRECTORY")

        if not endpoint or not bucket or not directory:
            raise ValueError("oss endpoint or bucket or directory is not set")

        auth = oss2.Auth(ak, sk)

        self._bucket = oss2.Bucket(auth, endpoint, bucket)
        self._oss_dir = directory

    async def upload_file_and_sign(
        self,
        local_path: str,
        expire_seconds: int = 3600,
    ) -> str:
        filename = os.path.basename(local_path)
        local_path = os.path.expanduser(local_path)
        remote_path = os.path.join(self._oss_dir, filename).replace("\\", "/")
        self._bucket.put_object_from_file(remote_path, local_path)
        return self._bucket.sign_url("GET", remote_path, expire_seconds)


if __name__ == "__main__":
    client = OssClient()
    signed_url = client.upload_file_and_sign("~/Downloads/dog_and_girl.jpeg")
    print(f"Signed URL: {signed_url}")
