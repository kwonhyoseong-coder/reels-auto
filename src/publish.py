"""
4-5단계: MP4를 S3/R2에 업로드 후 Instagram Graph API로 릴스 발행
- POST /{ig-user-id}/media  (video_url, media_type=REELS, caption)
- POST /{ig-user-id}/media_publish  (creation_id)
- 게시 전 container status가 FINISHED인지 확인
"""
import os
import time
from pathlib import Path

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://graph.facebook.com/v21.0"


def upload_to_s3(local_path: Path, key: str | None = None) -> str:
    key = key or local_path.name
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        region_name=os.getenv("S3_REGION", "auto"),
    )
    bucket = os.getenv("S3_BUCKET")
    s3.upload_file(
        str(local_path), bucket, key,
        ExtraArgs={"ContentType": "video/mp4", "CacheControl": "public, max-age=31536000"},
    )
    return f"{os.getenv('S3_PUBLIC_BASE').rstrip('/')}/{key}"


def create_reel_container(video_url: str, caption: str, ig_user_id: str, token: str) -> str:
    r = requests.post(f"{API}/{ig_user_id}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": token,
        "share_to_feed": "true",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def wait_container(container_id: str, token: str, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{API}/{container_id}", params={
            "fields": "status_code,status",
            "access_token": token,
        }, timeout=30)
        r.raise_for_status()
        data = r.json()
        code = data.get("status_code")
        print("  container:", code, data.get("status", ""))
        if code == "FINISHED":
            return True
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container failed: {data}")
        time.sleep(5)
    raise TimeoutError("Container status timeout")


def publish(container_id: str, ig_user_id: str, token: str) -> dict:
    r = requests.post(f"{API}/{ig_user_id}/media_publish", data={
        "creation_id": container_id,
        "access_token": token,
    }, timeout=30)
    r.raise_for_status()
    return r.json()


def publish_reel(local_mp4: Path, caption: str, key: str | None = None) -> dict:
    print("↑ S3 업로드 중...")
    video_url = upload_to_s3(local_mp4, key)
    print("  →", video_url)

    ig_user_id = os.getenv("IG_USER_ID")
    token = os.getenv("FB_ACCESS_TOKEN")

    print("↑ 컨테이너 생성 중...")
    cid = create_reel_container(video_url, caption, ig_user_id, token)
    print("  container_id:", cid)
    wait_container(cid, token)

    print("↑ 발행 중...")
    result = publish(cid, ig_user_id, token)
    print("  ✅", result)
    return result


def build_caption(script: dict) -> str:
    tags = " ".join(script.get("hashtags", []))
    return (
        f"{script['hook']}\n\n"
        + "\n".join(f"• {b}" for b in script["body"])
        + f"\n\n{script['cta']}\n"
        + f"\n🔗 출처: {script.get('source_url','')}\n"
        + f"\n{tags}\n"
        + "\n#정부혜택 #꿀정보 #릴스"
    )


if __name__ == "__main__":
    import sys
    mp4 = Path(sys.argv[1])
    publish_reel(mp4, caption=sys.argv[2] if len(sys.argv) > 2 else "테스트 발행")
