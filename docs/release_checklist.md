# GeoQA Public Release Checklist

## Repository Hygiene

- [x] No tracked `__pycache__`
- [x] No tracked `node_modules`
- [x] No tracked frontend build output
- [x] No private delivery data identified in the release audit
- [x] Public docs contain no private local paths, private filenames, or private delivery archive names
- [x] Private/local test records are anonymized by role, geometry type, scale, and outcome
- [x] Large files reviewed
- [x] LICENSE added
- [x] Package metadata declares Apache-2.0
- [x] Third-party demo data provenance documented separately

## Python Engine

- [x] Unit tests pass
- [x] Problem catalog validation passes
- [x] README first-run command works

## Atlas

- [ ] Fresh `npm install` works in `apps/atlas`
- [x] `npm run build` passes from a clean Atlas source copy
- [x] `npm test --if-present` passes from a clean Atlas source copy
- [x] `npm run audit:bloat --if-present` passes from a clean Atlas source copy
- [x] Idle safety check passes from a clean Atlas source copy
- [x] Top navigation links work
- [x] Footer text is clean and not sticky
- [x] Dataset pages are not sampled
- [x] Run QA public demo limits verified
- [ ] README includes Atlas screenshot
- [ ] Visual assets are public-safe and compressed
- [ ] No private filenames or local paths appear in screenshots/PDF

## Vercel

- [x] Root Directory documented as `apps/atlas`
- [x] Build Command documented as `npm run build`
- [x] Output Directory documented as `dist`
- [ ] Public demo sampling confirmed after deployment
- [x] Full validation copy does not imply hosted full backend
