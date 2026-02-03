# Documentation Index

Complete documentation for Amplifier App Utils.

## 📚 Documentation Structure

### Core Documentation

1. **[README.md](README.md)** - Main documentation
   - Overview and features
   - API endpoint reference
   - Quick examples
   - Configuration
   - Troubleshooting

2. **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
   - Prerequisites
   - Installation steps
   - First request
   - Quick validation

3. **[SETUP.md](SETUP.md)** - Production deployment
   - Docker deployment
   - Security checklist
   - Monitoring setup
   - Backup strategy
   - Upgrading local forks

4. **[TESTING.md](TESTING.md)** - Test suite guide
   - Test commands
   - Test categories
   - Coverage details
   - Smoke test API

5. **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Architecture details
   - Implementation overview
   - File structure
   - Design decisions
   - CLI to API mapping

---

## 🚀 Getting Started Path

**New users:** Start here
1. Read [README.md](README.md) - Understand what it does
2. Follow [QUICKSTART.md](QUICKSTART.md) - Get it running
3. Test it works - Run smoke tests

**Deploying to production:** 
1. Read [SETUP.md](SETUP.md) - Production checklist
2. Configure security settings
3. Deploy with Docker

**Developers:**
1. Read [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Understand architecture
2. Read [TESTING.md](TESTING.md) - Run test suite
3. Check API docs at `/docs` endpoint

---

## 📖 Quick References

### Start the Service
```bash
./run-dev.sh
```

### Run Tests
```bash
.venv/bin/python -m pytest tests/test_database.py tests/test_models.py -v
```

### API Documentation
```
http://localhost:8765/docs
```

### Test via API
```bash
curl http://localhost:8765/smoke-tests/quick
```

---

## 📁 File Structure

```
amplifier-app-utils/
├── README.md                        # ← Start here
├── QUICKSTART.md                    # 5-minute setup
├── SETUP.md                         # Production guide
├── TESTING.md                       # Test suite
├── IMPLEMENTATION_SUMMARY.md        # Architecture
├── DOCUMENTATION_INDEX.md           # This file
├── .env.example                     # Config template
├── pyproject.toml                   # Dependencies
├── amplifier_app_utils/             # Source code
└── tests/                           # Test suite
```

---

## 🔗 External Resources

- [amplifier-core](https://github.com/microsoft/amplifier-core) - Kernel
- [amplifier-foundation](https://github.com/microsoft/amplifier-foundation) - Foundation
- [amplifier-app-cli](https://github.com/microsoft/amplifier-app-cli) - CLI reference

---

**All documentation is up-to-date as of 2026-02-03**
