import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Add session cookie security after app.secret_key line
old = 'app.config["MAX_CONTENT_LENGTH"]'
new = 'app.config["SESSION_COOKIE_SECURE"] = True\napp.config["SESSION_COOKIE_HTTPONLY"] = True\napp.config["SESSION_COOKIE_SAMESITE"] = "Lax"\napp.config["MAX_CONTENT_LENGTH"]'
content = content.replace(old, new)

# 2. Add missing security headers after Referrer-Policy line
old_header = '    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"'
new_header = '    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"\n    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"\n    response.headers["X-XSS-Protection"] = "1; mode=block"\n    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"'
content = content.replace(old_header, new_header)

# 3. Restrict CORS from wildcard to specific origins
old_cors = '    response.headers["Access-Control-Allow-Origin"] = "*"'
new_cors = '    origin = request.headers.get("Origin", "")\n    allowed_origins = ["https://website-auditor.io", "https://spikeycoder.github.io", "http://localhost:5000"]\n    if origin in allowed_origins:\n        response.headers["Accacte s>s -fCioxn_tsreoclu-rAiltlyo.wp-yO r<i<g i'nP"Y]E O=F 'o
riimgpionr\tn  r e 
 
ewlisteh: \onp e n ( ' a p p .rpeys'p,o n'sre'.)h eaasd efr:s
[ " A c cceosnst-eCnotn t=r ofl.-rAelaldo(w)-
O
r#i g1i.n "A]d d=  s"ehststiposn: /c/owoekbisei tsee-cauurdiittyo ra.fitoe"r' 
acpopn.tseenctr e=t _ckoenyt elnitn.er
eopllda c=e ('oalpdp_.ccoornsf,i gn[e"wM_AcXo_rCsO)N
T
EwNiTt_hL EoNpGeTnH("']a'p
pn.epwy '=,  ''awp'p). caosn ffi:g
[ " S E SfS.IwOrNi_tCeO(OcKoInEt_eSnEtC)U
R
Ep"r]i n=t (T'rAulel\ nsaepcpu.rciotnyf ifgi[x"eSsE SaSpIpOlNi_eCdO OsKuIcEc_eHsTsTfPuOlNlLyY'")]
 P=Y ETOrFu
e\napp.config["SESSION_COOKIE_SAMESITE"] = "Lax"\napp.config["MAX_CONTENT_LENGTH"]'
content = content.replace(old, new)

# 2. Add missing security headers after Referrer-Policy line
old_header = '    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"'
new_header = '    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"\n    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"\n    response.headers["X-XSS-Protection"] = "1; mode=block"\n    response.headers["Permissions-Policy"] = "camer
a=(), microphone=(), geolocation=()"'
content = content.replace(old_header, new_header)

# 3. Restrict CORS from wildcard to specific origins
old_cors = '    response.headers["Access-Control-Allow-Origin"] = "*"'
new_cors = '    origin = request.headers.get("Origin", "")\n    allowed_origins = ["https://website-auditor.io", "https://spikeycoder.github.io", "http://localhost:5000"]\n    if origin in allowed_origins:\n        response.headers["Access-Control-Allow-Origin"] = origin\n    else:\n        response.headers["Access-Control-Allow-Origin"] = "https://website-auditor.io"'
content = content.replace(old_cors, new_cors)

with open('app.py', 'w') as f:
    f.write(content)

print('All security fixes applied successfully')
