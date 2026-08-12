# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for the lazy loading of ``azurefunctions.extensions.base``.

The v2 runtime defers importing the base extension until first use to
avoid paying its (200+ ms) cold-import cost for apps that don't use
deferred bindings or HTTP v2. These tests pin down that contract:

* ``load_binding_registry`` must NOT import the base extension.
* ``_get_deferred_binding_registry`` must short-circuit to ``None``
  when the base extension is not already in ``sys.modules``.
* ``_get_deferred_binding_registry`` caches its result so the import
  attempt happens at most once.
* ``HttpV2Registry._check_http_v2_enabled`` must return ``False``
  without importing the base extension when it is not in
  ``sys.modules``.
* The deferred-binding consumers (``get_binding``,
  ``check_deferred_bindings_enabled``) gracefully fall back when the
  registry is unavailable.
"""
import sys
import types
import unittest
from unittest import mock

from azure_functions_runtime.bindings import meta
from azure_functions_runtime.http_v2 import HttpV2Registry


def _reset_meta_state():
    """Restore meta module state between tests."""
    meta.DEFERRED_BINDING_REGISTRY = None
    meta._DEFERRED_BINDING_REGISTRY_LOADED = False


def _reset_http_v2_state():
    """Restore HttpV2Registry class state between tests."""
    HttpV2Registry._http_v2_enabled = False
    HttpV2Registry._ext_base = None
    HttpV2Registry._http_v2_enabled_checked = False


class TestLoadBindingRegistryNoEagerExtImport(unittest.TestCase):
    """``load_binding_registry`` must not import the base extension."""

    def setUp(self):
        _reset_meta_state()

    def tearDown(self):
        _reset_meta_state()

    def test_load_binding_registry_does_not_import_base_extension(self):
        # The base extension must remain absent from sys.modules after
        # load_binding_registry runs. We patch the import machinery to
        # raise if anything tries to import azurefunctions.extensions.base
        # during this call, which catches even transitive imports.
        real_import = __builtins__['__import__'] if isinstance(
            __builtins__, dict) else __builtins__.__import__
        seen_base_import = []

        def tracking_import(name, *args, **kwargs):
            if name == 'azurefunctions.extensions.base' or name.startswith(
                    'azurefunctions.extensions.base.'):
                seen_base_import.append(name)
            return real_import(name, *args, **kwargs)

        # Pop base extension from sys.modules so any import would be
        # observed (no cached version).
        removed = {
            k: sys.modules.pop(k)
            for k in list(sys.modules)
            if k == 'azurefunctions.extensions.base'
            or k.startswith('azurefunctions.extensions.base.')
        }
        try:
            with mock.patch('builtins.__import__', side_effect=tracking_import):
                meta.load_binding_registry()
        finally:
            sys.modules.update(removed)

        self.assertEqual(
            seen_base_import, [],
            msg='load_binding_registry should not import '
                'azurefunctions.extensions.base. Saw imports: '
                f'{seen_base_import}',
        )

    def test_load_binding_registry_populates_binding_registry(self):
        # The customer-facing azure.functions registry must still be
        # populated unconditionally — only the base extension load is
        # deferred.
        meta.BINDING_REGISTRY = None
        meta.load_binding_registry()
        self.assertIsNotNone(
            meta.BINDING_REGISTRY,
            msg='BINDING_REGISTRY must be populated even though the '
                'base extension load is deferred.',
        )


class TestGetDeferredBindingRegistry(unittest.TestCase):
    """Behaviour of the lazy ``_get_deferred_binding_registry`` helper."""

    # Sentinel used by _restore_module_state to indicate that the attribute
    # did not exist before we set it.
    _MISSING = object()

    def setUp(self):
        _reset_meta_state()
        # Stash any pre-existing entries for the entire azurefunctions.* tree
        # we touch, plus the attribute values on parent packages. This is
        # critical on Linux CI where the real azurefunctions.extensions
        # package is installed and used by other test files. Without it we
        # would leave a stale MagicMock at azurefunctions.extensions.base,
        # which leaks to subsequent tests that do `import
        # azurefunctions.extensions.base as x` and pick up the MagicMock
        # via parent-package attribute traversal.
        self._stashed_modules = {}
        for key in list(sys.modules):
            if (key == 'azurefunctions'
                    or key == 'azurefunctions.extensions'
                    or key == 'azurefunctions.extensions.base'
                    or key.startswith('azurefunctions.extensions.base.')):
                self._stashed_modules[key] = sys.modules.pop(key)
        self._saved_attrs = []

    def tearDown(self):
        _reset_meta_state()
        self._restore_module_state()

    def _save_attr(self, module_name, attr_name):
        """Snapshot module.attr so it can be restored verbatim later."""
        module = sys.modules.get(module_name)
        if module is None:
            return
        if hasattr(module, attr_name):
            self._saved_attrs.append(
                (module_name, attr_name, getattr(module, attr_name))
            )
        else:
            self._saved_attrs.append(
                (module_name, attr_name, self._MISSING)
            )

    def _restore_module_state(self):
        """Reverse the mutations made by _install_fake_base_extension.

        Restores parent-package attributes first (so any sys.modules
        restore below picks up the right object), then pops any
        leftover fake modules, then re-inserts the originals.
        """
        for module_name, attr_name, original in self._saved_attrs:
            module = sys.modules.get(module_name)
            if module is None:
                continue
            if original is self._MISSING:
                try:
                    delattr(module, attr_name)
                except AttributeError:
                    pass
            else:
                setattr(module, attr_name, original)
        self._saved_attrs = []

        for key in list(sys.modules):
            if (key == 'azurefunctions'
                    or key == 'azurefunctions.extensions'
                    or key == 'azurefunctions.extensions.base'
                    or key.startswith('azurefunctions.extensions.base.')):
                sys.modules.pop(key, None)
        sys.modules.update(self._stashed_modules)

    def _install_fake_base_extension(self, fake_module):
        """Place fake_module at sys.modules['azurefunctions.extensions.base']
        AND wire up its parent packages so ``import azurefunctions.extensions
        .base as clients`` resolves ``clients`` to fake_module without
        touching disk.

        The ``as`` form of import does attribute lookup on the parent
        package after ``__import__`` returns, so the parents must be real
        modules with the expected attribute set (MagicMocks autogenerate
        a fresh child for any attribute access, which would shadow our
        fake_module).

        Parent-module attributes that we overwrite are recorded for
        restoration in tearDown.
        """
        # Build the namespace-package chain if absent. setUp already
        # popped any real azurefunctions/* entries into _stashed_modules,
        # so these inserts are guaranteed to be clean adds.
        if 'azurefunctions' not in sys.modules:
            sys.modules['azurefunctions'] = types.ModuleType('azurefunctions')
        if 'azurefunctions.extensions' not in sys.modules:
            sys.modules['azurefunctions.extensions'] = types.ModuleType(
                'azurefunctions.extensions')

        # Snapshot the attributes we are about to overwrite so tearDown
        # can put them back exactly as they were.
        self._save_attr('azurefunctions', 'extensions')
        self._save_attr('azurefunctions.extensions', 'base')

        sys.modules['azurefunctions'].extensions = \
            sys.modules['azurefunctions.extensions']
        sys.modules['azurefunctions.extensions'].base = fake_module
        sys.modules['azurefunctions.extensions.base'] = fake_module

    def test_short_circuits_when_base_extension_not_in_sys_modules(self):
        # Customer hasn't loaded any azurefunctions.extensions.* package,
        # so the helper must return None without attempting an import.
        self.assertNotIn('azurefunctions.extensions.base', sys.modules)

        def fail_on_import(name, *args, **kwargs):
            if name == 'azurefunctions.extensions.base':
                raise AssertionError(
                    'Helper attempted to import the base extension despite '
                    'the sys.modules short-circuit')
            return _real_import(name, *args, **kwargs)

        _real_import = __builtins__['__import__'] if isinstance(
            __builtins__, dict) else __builtins__.__import__

        with mock.patch('builtins.__import__', side_effect=fail_on_import):
            result = meta._get_deferred_binding_registry()

        self.assertIsNone(result)
        self.assertTrue(meta._DEFERRED_BINDING_REGISTRY_LOADED)

    def test_loads_registry_when_base_extension_already_imported(self):
        # Simulate the customer's code having imported the base extension
        # transitively (e.g. via azurefunctions.extensions.bindings.blob).
        fake_registry = mock.Mock(name='fake_registry')
        fake_module = mock.MagicMock()
        fake_module.get_binding_registry.return_value = fake_registry
        self._install_fake_base_extension(fake_module)

        result = meta._get_deferred_binding_registry()

        self.assertIs(result, fake_registry)
        self.assertIs(meta.DEFERRED_BINDING_REGISTRY, fake_registry)

    def test_result_is_cached_on_success(self):
        fake_registry = mock.Mock(name='fake_registry')
        fake_module = mock.MagicMock()
        fake_module.get_binding_registry.return_value = fake_registry
        self._install_fake_base_extension(fake_module)

        first = meta._get_deferred_binding_registry()
        # Drop the module again; cached value must still be returned.
        sys.modules.pop('azurefunctions.extensions.base', None)
        second = meta._get_deferred_binding_registry()

        self.assertIs(first, second)
        # get_binding_registry should only be invoked once across calls.
        fake_module.get_binding_registry.assert_called_once()

    def test_negative_result_is_cached(self):
        # When the short-circuit fires, subsequent calls must NOT retry
        # the import even if the customer later loads something that
        # would pull in the base extension.
        self.assertNotIn('azurefunctions.extensions.base', sys.modules)

        first = meta._get_deferred_binding_registry()
        self.assertIsNone(first)
        self.assertTrue(meta._DEFERRED_BINDING_REGISTRY_LOADED)

        # Now pretend the base extension has appeared. The cached "no"
        # result wins to avoid repeated import work in the hot path.
        fake_module = mock.MagicMock()
        fake_module.get_binding_registry.return_value = mock.Mock()
        self._install_fake_base_extension(fake_module)

        second = meta._get_deferred_binding_registry()

        self.assertIsNone(second)
        fake_module.get_binding_registry.assert_not_called()

    def test_direct_assignment_to_registry_is_honored(self):
        # Existing tests (e.g. test_deferred_bindings) set
        # meta.DEFERRED_BINDING_REGISTRY directly. The helper must
        # honor that value without re-importing.
        sentinel = mock.Mock(name='preset')
        meta.DEFERRED_BINDING_REGISTRY = sentinel

        def fail_on_import(name, *args, **kwargs):
            if name == 'azurefunctions.extensions.base':
                raise AssertionError(
                    'Helper attempted to import despite preset registry')
            return _real_import(name, *args, **kwargs)

        _real_import = __builtins__['__import__'] if isinstance(
            __builtins__, dict) else __builtins__.__import__

        with mock.patch('builtins.__import__', side_effect=fail_on_import):
            result = meta._get_deferred_binding_registry()

        self.assertIs(result, sentinel)


class TestCheckDeferredBindingsEnabledFallback(unittest.TestCase):
    """``check_deferred_bindings_enabled`` must not error when the
    registry is unavailable; it must return the pass-through values."""

    def setUp(self):
        _reset_meta_state()
        self._stashed_modules = {
            k: sys.modules.pop(k)
            for k in list(sys.modules)
            if k == 'azurefunctions.extensions.base'
            or k.startswith('azurefunctions.extensions.base.')
        }

    def tearDown(self):
        _reset_meta_state()
        sys.modules.update(self._stashed_modules)

    def test_returns_passthrough_when_extension_unavailable(self):
        # Common case for the regression we fixed: a function with a
        # plain HttpRequest annotation triggers this call for each
        # parameter during indexing. It must NOT load the extension.
        self.assertNotIn('azurefunctions.extensions.base', sys.modules)

        enabled, is_deferred = meta.check_deferred_bindings_enabled(
            str, deferred_bindings_enabled=False)
        self.assertFalse(enabled)
        self.assertFalse(is_deferred)

        enabled, is_deferred = meta.check_deferred_bindings_enabled(
            str, deferred_bindings_enabled=True)
        self.assertTrue(enabled)
        self.assertFalse(is_deferred)

        self.assertNotIn(
            'azurefunctions.extensions.base', sys.modules,
            msg='check_deferred_bindings_enabled triggered an import '
                'of the base extension on a non-deferred path.',
        )


class TestGetBindingDeferredFallback(unittest.TestCase):
    """``get_binding`` with ``is_deferred_binding=True`` must not crash
    when the registry is unavailable."""

    def setUp(self):
        _reset_meta_state()
        # Ensure the regular binding registry exists for non-deferred
        # lookups (load_binding_registry populates it).
        meta.load_binding_registry()
        self._stashed_modules = {
            k: sys.modules.pop(k)
            for k in list(sys.modules)
            if k == 'azurefunctions.extensions.base'
            or k.startswith('azurefunctions.extensions.base.')
        }

    def tearDown(self):
        _reset_meta_state()
        sys.modules.update(self._stashed_modules)

    def test_deferred_lookup_falls_back_to_generic(self):
        # Without the extension installed, deferred lookups should
        # silently return GenericBinding rather than throwing
        # AttributeError on DEFERRED_BINDING_REGISTRY.get.
        result = meta.get_binding(
            'unknown_deferred_binding', is_deferred_binding=True)
        from azure_functions_runtime.bindings.generic import GenericBinding
        self.assertIs(result, GenericBinding)


class TestHttpV2RegistryShortCircuit(unittest.TestCase):
    """``HttpV2Registry._check_http_v2_enabled`` must not import the
    base extension when it is not already in ``sys.modules``."""

    # Sentinel for attribute snapshots (see _save_attr).
    _MISSING = object()

    def setUp(self):
        _reset_http_v2_state()
        # See TestGetDeferredBindingRegistry.setUp for the rationale. We
        # stash entries across the full azurefunctions.* tree we touch
        # and snapshot the parent-package attributes we will overwrite,
        # so tearDown can put everything back exactly as it was. This
        # prevents test pollution on Linux CI where the real
        # azurefunctions.extensions package is installed.
        self._stashed_modules = {}
        for key in list(sys.modules):
            if (key == 'azurefunctions'
                    or key == 'azurefunctions.extensions'
                    or key == 'azurefunctions.extensions.base'
                    or key.startswith('azurefunctions.extensions.base.')):
                self._stashed_modules[key] = sys.modules.pop(key)
        self._saved_attrs = []

    def tearDown(self):
        _reset_http_v2_state()
        self._restore_module_state()

    def _save_attr(self, module_name, attr_name):
        module = sys.modules.get(module_name)
        if module is None:
            return
        if hasattr(module, attr_name):
            self._saved_attrs.append(
                (module_name, attr_name, getattr(module, attr_name))
            )
        else:
            self._saved_attrs.append(
                (module_name, attr_name, self._MISSING)
            )

    def _restore_module_state(self):
        for module_name, attr_name, original in self._saved_attrs:
            module = sys.modules.get(module_name)
            if module is None:
                continue
            if original is self._MISSING:
                try:
                    delattr(module, attr_name)
                except AttributeError:
                    pass
            else:
                setattr(module, attr_name, original)
        self._saved_attrs = []

        for key in list(sys.modules):
            if (key == 'azurefunctions'
                    or key == 'azurefunctions.extensions'
                    or key == 'azurefunctions.extensions.base'
                    or key.startswith('azurefunctions.extensions.base.')):
                sys.modules.pop(key, None)
        sys.modules.update(self._stashed_modules)

    def _install_fake_base_extension(self, fake_module):
        """See TestGetDeferredBindingRegistry._install_fake_base_extension."""
        if 'azurefunctions' not in sys.modules:
            sys.modules['azurefunctions'] = types.ModuleType('azurefunctions')
        if 'azurefunctions.extensions' not in sys.modules:
            sys.modules['azurefunctions.extensions'] = types.ModuleType(
                'azurefunctions.extensions')

        self._save_attr('azurefunctions', 'extensions')
        self._save_attr('azurefunctions.extensions', 'base')

        sys.modules['azurefunctions'].extensions = \
            sys.modules['azurefunctions.extensions']
        sys.modules['azurefunctions.extensions'].base = fake_module
        sys.modules['azurefunctions.extensions.base'] = fake_module

    def test_returns_false_without_importing_when_extension_absent(self):
        self.assertNotIn('azurefunctions.extensions.base', sys.modules)

        def fail_on_import(name, *args, **kwargs):
            if name == 'azurefunctions.extensions.base':
                raise AssertionError(
                    'HttpV2Registry attempted to import the base extension '
                    'despite the sys.modules short-circuit')
            return _real_import(name, *args, **kwargs)

        _real_import = __builtins__['__import__'] if isinstance(
            __builtins__, dict) else __builtins__.__import__

        with mock.patch('builtins.__import__', side_effect=fail_on_import):
            self.assertFalse(HttpV2Registry.http_v2_enabled())

        self.assertNotIn('azurefunctions.extensions.base', sys.modules)

    def test_uses_extension_when_already_imported(self):
        # Simulate the customer's FastAPI extension having loaded the
        # base extension; the registry must consult its feature checker.
        fake_checker = mock.MagicMock()
        fake_checker.http_v2_enabled.return_value = True
        fake_module = mock.MagicMock()
        fake_module.HttpV2FeatureChecker = fake_checker
        self._install_fake_base_extension(fake_module)

        self.assertTrue(HttpV2Registry.http_v2_enabled())

        fake_checker.http_v2_enabled.assert_called_once()

    def test_cached_result_skips_subsequent_checks(self):
        # First call sets the cache; second call must not reconsult
        # sys.modules or call the feature checker.
        fake_checker = mock.MagicMock()
        fake_checker.http_v2_enabled.return_value = True
        fake_module = mock.MagicMock()
        fake_module.HttpV2FeatureChecker = fake_checker
        self._install_fake_base_extension(fake_module)

        first = HttpV2Registry.http_v2_enabled()
        second = HttpV2Registry.http_v2_enabled()

        self.assertTrue(first)
        self.assertTrue(second)
        fake_checker.http_v2_enabled.assert_called_once()


if __name__ == '__main__':
    unittest.main()
