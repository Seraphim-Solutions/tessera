#!/usr/bin/env python3
import hmac
import hashlib
import urllib.parse
import json
import re

# https://github.com/yazeed44/social-media-detector-api/blob/master/yocial/features/Instagram/Instagram.py
IG_SIG_KEY = 'e6358aeede676184b9fe702b30f4fd35e71744605e39d2181a34cede076b3c33'


def ig_sig_v4(headers, query, body, context, **kwargs):
    """Instagram signed body (v4) pre-request hook.

    Parameters:
        headers (dict): current headers
        query (dict): current query params
        body (dict): current body fields (templated already)
        context (dict): context with items like 'phone' (and optionally country_code)
        **kwargs: ignored extra signer params for forward-compatibility

    Returns:
        tuple(dict, dict, dict): (headers, query, body) after mutation
    """
    # Normalize phone: keep leading '+' if present, remove spaces/formatting
    phone_raw = context.get('phone', '') or ''
    digits = re.sub(r"\D+", "", str(phone_raw))
    # Allow descriptor to choose q formatting via signer_params
    # q_format: 'plus' -> "+<digits>", 'digits' -> "<digits>"
    q_format = str(kwargs.get('q_format', 'plus')).lower()
    if q_format == 'digits':
        q_value = digits
    else:
        q_value = f"+{digits}" if digits else ""

    # Compose the body used for signing (override q with normalized value)
    composed = dict(body or {})
    composed['q'] = q_value

    # Build JSON payload exactly like typical Python default dumps
    # (matches the reference implementation which does not tweak separators/ensure_ascii)
    payload = json.dumps(composed)
    signature = hmac.new(IG_SIG_KEY.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    signed_body = f"{signature}.{urllib.parse.quote_plus(payload)}"

    # Build the exact form body string to avoid double-encoding by requests
    version = str((body or {}).get('ig_sig_key_version', '4'))
    new_body = f"ig_sig_key_version={version}&signed_body={signed_body}"

    # Ensure content-type is form-urlencoded; other headers are provided by descriptor
    headers = {**headers, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
    return headers, query, new_body
