"""Public link endpoints: Android App Links verification and the browser fallback for invite/QR links.

When the app is installed, Android opens `/i/...` and `/q/...` links in the app directly (verified through
assetlinks.json). Otherwise the browser lands on a small page pointing to the app. These pages never look up
the token, so they reveal nothing about it.
"""
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.config import Settings, get_settings

router = APIRouter(tags=["links"], include_in_schema=False)

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GardenTender</title>
<style>body{{font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem;line-height:1.5}}
a.button{{display:inline-block;padding:.75rem 1.25rem;border-radius:.5rem;background:#2e7d32;color:#fff;text-decoration:none}}</style>
</head><body>
<h1>{heading}</h1>
<p>{body}</p>
<p><a class="button" href="https://play.google.com/store/apps/details?id={package}">Get GardenTender</a></p>
<p>Already installed? Open this link on your phone and it will open in the app.</p>
</body></html>"""


def _page(heading: str, body: str, settings: Settings) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(heading=escape(heading), body=escape(body), package=escape(settings.android_package)))


@router.get("/.well-known/assetlinks.json")
async def assetlinks(settings: Settings = Depends(get_settings)):
    if not settings.android_cert_sha256:
        raise HTTPException(404, "App Links are not configured (set ANDROID_CERT_SHA256).")
    return [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": settings.android_package,
                "sha256_cert_fingerprints": settings.android_cert_sha256,
            },
        }
    ]


@router.get("/i/{token}", response_class=HTMLResponse)
async def invite_page(token: str, settings: Settings = Depends(get_settings)):
    return _page("You've been invited to a garden", "Open this invite in the GardenTender app to join.", settings)


@router.get("/q/{token}", response_class=HTMLResponse)
async def qr_page(token: str, settings: Settings = Depends(get_settings)):
    return _page("GardenTender", "This code opens a garden or plant in the GardenTender app.", settings)
