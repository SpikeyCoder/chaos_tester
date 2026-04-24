from PIL import Image, ImageDraw, ImageFont
w, h = 1200, 630
img = Image.new('RGB', (w, h), color=(15, 23, 42))
d = ImageDraw.Draw(img)
d.rectangle([0, 0, w, 4], fill=(56, 189, 248))
d.rectangle([0, h-4, w, h], fill=(56, 189, 248))
try:
    f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 52)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
    f3 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
except Exception:
    f = f2 = f3 = ImageFont.load_default()
d.text((600, 200), 'Website Auditor', fill=(56, 189, 248), font=f, anchor='mm')
d.text((600, 270), 'One-Click Website Audit Tool', fill=(203, 213, 225), font=f2, anchor='mm')
for i, p in enumerate(['SEO Analysis', 'Broken Links', 'Security Scan', 'Form Testing']):
    x = 200 + i * 250
    bb = d.textbbox((0, 0), p, font=f3)
    pw = bb[2] - bb[0]
    d.rounded_rectangle([x-pw//2-16, 340, x+pw//2+16, 376], radius=18, fill=(30, 41, 59), outline=(56, 189, 248))
    d.text((x, 358), p, fill=(56, 189, 248), font=f3, anchor='mm')
d.text((600, 470), 'Instant reports. No login required.', fill=(74, 222, 128), font=f2, anchor='mm')
d.text((600, 540), 'website-auditor.io', fill=(100, 116, 139), font=f2, anchor='mm')
img.save('static/og-image.png')
print('OG image saved to static/og-image.png')
