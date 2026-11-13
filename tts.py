import time
import requests

from config import TTS_API_KEY

BASE_URL = "https://api.tts.ai/v1"

HEADERS = {
    "Authorization": f"Bearer {TTS_API_KEY}",
    "Content-Type": "application/json",
}


def get_voices():
    """Return voices as (name, id) tuples, English voices first."""
    response = requests.get(
        f"{BASE_URL}/voices/",
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()
    raw = data.get("voices", [])
    voices = []
    for v in raw:
        if isinstance(v, dict):
            voices.append((v.get("name") or v.get("id"), v.get("id")))
        else:
            voices.append((v, v))
    # English voices first so the default page is relevant for most users
    voices.sort(key=lambda t: 0 if str(t[1]).startswith(("en", "v2/en")) else 1)
    return voices


def _fetch_audio_bytes(audio_url):
    audio = requests.get(audio_url, timeout=60)
    audio.raise_for_status()
    return audio.content


def generate_speech(text, voice):
    """Generate speech and return a result dict.

    Returns:
        {"success": True, "audio": <bytes>} on success
        {"success": False, "error": "<message>"} on failure
    """
    try:
        response = requests.post(
            f"{BASE_URL}/tts/",
            headers=HEADERS,
            json={
                "model": "kokoro",
                "text": text,
                "voice": voice,
                "format": "mp3"
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()
        job_uuid = data.get("uuid")

        if not job_uuid:
            raise RuntimeError("No TTS job ID was returned.")

        for _ in range(60):
            result = requests.get(
                f"{BASE_URL}/speech/results/",
                params={"uuid": job_uuid},
                headers=HEADERS,
                timeout=30
            )

            result.raise_for_status()
            result_data = result.json()

            status = result_data.get("status")

            if status == "completed":
                audio_url = result_data.get("result_url")

                if not audio_url:
                    raise RuntimeError("No audio URL was returned.")

                return {"success": True, "audio": _fetch_audio_bytes(audio_url)}

            if status == "failed":
                raise RuntimeError(
                    result_data.get("error", "TTS generation failed.")
                )

            time.sleep(1.5)

        raise TimeoutError("TTS generation timed out.")

    except requests.HTTPError as e:
        return {"success": False, "error": f"TTS service error: {e.response.status_code}"}
    except (requests.RequestException, RuntimeError, TimeoutError) as e:
        return {"success": False, "error": str(e)}
