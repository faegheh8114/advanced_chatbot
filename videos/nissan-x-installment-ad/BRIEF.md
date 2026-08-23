---
workflow: general-video
flow: automation
storyboard: no
message: "The Nissan X Tak-Souz pickup transforms from base gray to a custom diamond-turquoise finish in a CGI-style configurator reveal, then cuts to an urgent installment sales offer"
destination: instagram-reels
aspect: 1080x1920
language: fa
length: 15s
angle: concept
---

## Intent

A vertical (9:16) Instagram Reels-style car-configurator ad for the Nissan X
Tak-Souz pickup, modeled directly on a reference reel: beach/palm setting,
floating glassmorphism spec card, floating color orbs selected by a hand
gesture, cinematic orbit/zoom camera moves, wheel/hood close-ups, and a
final rear three-quarter shot with exhaust flame and sand dust. Golden-hour
lighting, high-contrast, glossy CGI-game-render look.

The piece then makes a hard dramatic cut (glitch/RGB-split transition) into
a second scene: a laptop being opened in a dark, minimal office, screen glow
lighting the hands, and a final full-screen reveal of Nissan installment
("اقساطی") sale terms and dealership contact info in Persian, with a
line-by-line reveal animation.

Full shot-by-shot direction, exact Persian sale-terms copy, and technical
notes (camera language, sound design, typography, palette, duration) are
given verbatim by the user in the attached prompt document — treat that
document as the authoritative script; do not re-interpret its shot list.

**Known constraint (stated to the user, not a brief field):** HyperFrames
renders HTML/CSS/JS DOM animation via headless Chrome + ffmpeg — it does not
generate true photoreal 3D CGI, hand/gesture footage, or a rotating 3D truck
model. The build approximates the reference's CGI-configurator *language*
(floating glass HUD, color-swap reveal, glow/particle overlays, glitch
transition, orbit-style pans on a 2D hero cutout, kinetic Persian
typography) using the supplied reference photo as the hero asset, not a
literal recreation of hand-operated color orbs or true camera orbit around
a 3D model.

## Assets

- /root/.claude/uploads/52ea7237-4d09-5c2d-a9ea-55a70476293f/89860c2e-image.png —
  6-panel reference photo sheet of the actual Nissan X Tak-Souz pickup
  (gray metallic, navy stripe, tri-color badge, black steel wheels); source
  for the cutout hero asset used across shots 1-4.
- /root/.claude/uploads/52ea7237-4d09-5c2d-a9ea-55a70476293f/43c97d7c-nissan_prompt.md —
  full Persian shot-by-shot script, sale-terms copy, and technical notes;
  authoritative source for all scene content and timing.

## Customizations

- Color-swap reveal: base gray metallic → "diamond turquoise / crushed
  diamond" finish, triggered by a glowing touch point, with the HUD
  material label updating in sync.
- Floating glassmorphism spec-card HUD (model name, edition, material).
- Line-by-line Persian text reveal with glow-outline on the final sales
  screen, ending on dealership contact + hashtags.

## Notes

- 9:16 vertical, 1080x1920, ~14-16s total, cinematic 24fps feel.
- Two-part structure: outdoor configurator reveal (~10s) → glitch cut →
  indoor laptop / sales-terms reveal (~5-6s).
- No literal human actor footage is available; the "hand" and "laptop
  hands" beats are stylized/suggested rather than live-action.
