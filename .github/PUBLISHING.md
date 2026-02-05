# Publishing to PyPI

This guide explains how to publish Devhost to PyPI using GitHub Actions.

## Prerequisites

1. **PyPI Account**: Create accounts on both [PyPI](https://pypi.org) and [TestPyPI](https://test.pypi.org)
2. **Trusted Publishing**: Configure trusted publishing for both PyPI and TestPyPI

### Setting up Trusted Publishing

#### For TestPyPI:
1. Go to https://test.pypi.org/manage/account/publishing/
2. Add a new pending publisher:
   - **PyPI Project Name**: `devhost`
   - **Owner**: `Sebastian Gomez`
   - **Repository URL**: `https://github.com/Patoruzuy/devhost`
   - **Repository name**: `Devhost`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `testpypi`

#### For PyPI (Production):
1. Go to https://pypi.org/manage/account/publishing/
2. Add a new pending publisher with the same settings but:
   - **Environment name**: `pypi`

## Release Process

### 1. Test Release (TestPyPI)

Test your package before publishing to production:

```bash
# Trigger manual workflow from GitHub Actions tab
# OR
git tag v2.1.0-rc1
git push origin v2.1.0-rc1
```

This will:
- Run all tests
- Build the package
- Publish to TestPyPI only

**Test the package**:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ devhost
```

### 2. Production Release (PyPI)

Once testing is complete:

```bash
# Update version in pyproject.toml and devhost_cli/__init__.py
# Commit changes
git add pyproject.toml devhost_cli/__init__.py CHANGELOG.md
git commit -m "Bump version to 2.1.0"

# Create and push tag
git tag v2.1.0
git push origin main
git push origin v2.1.0
```

This will:
- Run all tests on Python 3.10, 3.11, 3.12
- Build the package
- Publish to TestPyPI (for verification)
- Publish to PyPI (production)

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (v3.0.0): Breaking changes
- **MINOR** (v2.1.0): New features, backward compatible
- **PATCH** (v2.0.1): Bug fixes

**Pre-release versions**:
- **Release Candidate**: v2.1.0-rc1
- **Beta**: v2.1.0-beta1
- **Alpha**: v2.1.0-alpha1

## Manual Publishing (Fallback)

If GitHub Actions fails, you can publish manually:

```bash
# Install build tools
pip install build twine

# Build
python -m build

# Test upload
twine upload --repository testpypi dist/*

# Production upload
twine upload dist/*
```

## Troubleshooting

### "Project name already exists"
- You need to create the project on TestPyPI/PyPI first by uploading manually once
- Or configure trusted publishing as shown above

### "Invalid or non-existent authentication"
- Ensure trusted publishing is configured correctly
- Check that the workflow environment name matches

### "Version already exists"
- You cannot re-upload the same version
- Bump the version number and create a new tag

## Workflow Triggers

The publish workflow runs when:
- **Tags pushed** matching `v*` (e.g., v2.1.0)
- **Manual trigger** from GitHub Actions UI (TestPyPI only)

## Environments

GitHub repository environments provide additional security:

1. Go to Settings → Environments
2. Create `testpypi` and `pypi` environments
3. Add protection rules:
   - Required reviewers
   - Wait timer
   - Branch restrictions

## Verification

After publishing:

1. **Check PyPI page**: https://pypi.org/project/devhost/
2. **Test installation**:
   ```bash
   pip install devhost
   python -c "from devhost import create_devhost_app; print('OK')"
   ```
3. **Verify version**:
   ```bash
   pip show devhost
   ```

## GitHub Release

After publishing to PyPI, create a GitHub release:

1. Go to Releases → Draft a new release
2. Choose the tag (v2.1.0)
3. Title: "v2.1.0 - Description"
4. Description: Copy from CHANGELOG.md
5. Attach built wheel (.whl) and tarball (.tar.gz) from Actions artifacts
6. Publish release

---

**Next Steps**:
- Announce on social media
- Update documentation
- Notify users via mailing list
- Submit to Python Weekly
