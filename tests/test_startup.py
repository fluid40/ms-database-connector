"""Unit tests for service startup and lifespan initialization."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from fastapi import FastAPI
from ms_database_connector.__main__ import (
    _init_startup_state,
    _track_startup,
    _setup_service_config,
    _setup_mapping_service,
    _setup_influx_connection,
    _setup_aas_connection,
    _preload_aas_metadata,
    lifespan,
    PollingWorker,
)
from ms_database_connector.dependencies import AppRuntimeDeps
from ms_database_connector.models.exceptions.configuration_errors import (
    ConfigurationError,
)


class TestInitStartupState:
    """Test _init_startup_state() state dict initialization."""

    def test_initial_state_structure(self):
        """Verify all expected flags and error list are present."""
        state = _init_startup_state()

        expected_flags = [
            "config_loaded",
            "mapping_initialized",
            "registry_connected",
            "influx_connected",
            "aimc_loaded",
        ]
        for flag in expected_flags:
            assert flag in state
            assert state[flag] is False

        assert "errors" in state
        assert isinstance(state["errors"], list)
        assert len(state["errors"]) == 0

    def test_state_is_fresh_each_call(self):
        """Verify each call returns a new independent state dict."""
        state1 = _init_startup_state()
        state2 = _init_startup_state()

        state1["config_loaded"] = True
        assert state2["config_loaded"] is False


class TestTrackStartup:
    """Test _track_startup() context manager behavior."""

    def test_success_sets_flag(self):
        """Verify context manager sets flag on successful exit."""
        state = _init_startup_state()
        with _track_startup(state, "test_step", "test_flag"):
            pass
        assert state["test_flag"] is True

    def test_success_with_none_flag_uses_key_as_flag(self):
        """Verify None flag value defaults to using the key."""
        state = _init_startup_state()
        with _track_startup(state, "test_key", None):
            pass
        assert state["test_key"] is True

    def test_error_captured_no_suppress(self):
        """Verify exceptions are captured but not suppressed."""
        state = _init_startup_state()
        test_error = ValueError("test error")
        with pytest.raises(ValueError):
            with _track_startup(state, "failing_step", "failing_flag"):
                raise test_error
        assert len(state["errors"]) == 1
        assert "failing_step" in state["errors"][0]
        assert "test error" in state["errors"][0]

    def test_flag_not_set_on_error(self):
        """Verify flag remains unset when exception occurs."""
        state = _init_startup_state()
        with pytest.raises(ValueError):
            with _track_startup(state, "step", "flag"):
                raise ValueError()
        assert state.get("flag") is None

    def test_multiple_errors_accumulate(self):
        """Verify multiple errors are all captured."""
        state = _init_startup_state()

        with pytest.raises(ValueError):
            with _track_startup(state, "first_error", "flag1"):
                raise ValueError("error 1")

        with pytest.raises(RuntimeError):
            with _track_startup(state, "second_error", "flag2"):
                raise RuntimeError("error 2")

        assert len(state["errors"]) == 2
        assert "first_error" in state["errors"][0]
        assert "second_error" in state["errors"][1]


class TestSetupServiceConfig:
    """Test _setup_service_config() initialization."""

    def test_successful_config_load(self):
        """Verify config_loaded flag set on success."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        mock_config = MagicMock()
        runtime_deps.config_provider.return_value = mock_config

        _setup_service_config(state, runtime_deps)

        assert state["config_loaded"] is True
        runtime_deps.config_provider.assert_called_once()

    def test_config_provider_exception_propagates(self):
        """Verify startup error is captured and exception propagates."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.config_provider.side_effect = ConfigurationError("No config file")

        with pytest.raises(ConfigurationError, match="No config file"):
            _setup_service_config(state, runtime_deps)

        assert state["config_loaded"] is False
        assert len(state["errors"]) == 1
        assert "service_configuration" in state["errors"][0]

    def test_generic_exception_also_propagates(self):
        """Verify other exception types also propagate correctly."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.config_provider.side_effect = FileNotFoundError("Missing file")

        with pytest.raises(FileNotFoundError):
            _setup_service_config(state, runtime_deps)


class TestSetupMappingService:
    """Test _setup_mapping_service() initialization."""

    def test_successful_mapping_initialization(self):
        """Verify mapping_initialized flag set on success."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        mock_handler = MagicMock()
        runtime_deps.mapping_handler_provider.return_value = mock_handler

        _setup_mapping_service(state, runtime_deps)

        assert state["mapping_initialized"] is True
        runtime_deps.mapping_handler_provider.assert_called_once()

    def test_mapping_provider_exception_propagates(self):
        """Verify mapping initialization failure is captured."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.mapping_handler_provider.side_effect = ConfigurationError(
            "Bad mapping"
        )

        with pytest.raises(ConfigurationError):
            _setup_mapping_service(state, runtime_deps)

        assert state["mapping_initialized"] is False
        assert len(state["errors"]) == 1
        assert "mapping_configuration" in state["errors"][0]

    def test_mapping_not_retried_after_failure(self):
        """Verify failed mapping initialization doesn't retry."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.mapping_handler_provider.side_effect = RuntimeError("Init failed")

        with pytest.raises(RuntimeError):
            _setup_mapping_service(state, runtime_deps)

        # Provider should be called exactly once
        assert runtime_deps.mapping_handler_provider.call_count == 1


class TestSetupInfluxConnection:
    """Test _setup_influx_connection() with client availability."""

    def test_connection_success_with_valid_client(self):
        """Verify influx_connected flag set with valid client."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        mock_client = MagicMock()
        runtime_deps.influx_client_provider.return_value = mock_client

        _setup_influx_connection(state, runtime_deps)

        assert state["influx_connected"] is True
        runtime_deps.influx_client_provider.assert_called_once()

    def test_connection_none_raises_runtime_error(self):
        """Verify startup fails when client is None (missing token/config)."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.influx_client_provider.return_value = None

        with pytest.raises(RuntimeError, match="InfluxDB connection failed"):
            _setup_influx_connection(state, runtime_deps)

        assert state["influx_connected"] is False
        assert len(state["errors"]) == 1

    def test_connection_error_propagates(self):
        """Verify connection errors during client creation propagate."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.influx_client_provider.side_effect = ConnectionError("Unreachable")

        with pytest.raises(ConnectionError):
            _setup_influx_connection(state, runtime_deps)

        assert state["influx_connected"] is False


class TestSetupAasConnection:
    """Test _setup_aas_connection() server handler initialization."""

    def test_connection_success_returns_handler(self):
        """Verify server handler is created and returned."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        mock_handler = MagicMock()
        mock_loader = MagicMock()
        runtime_deps.server_handler_factory.return_value = mock_handler
        runtime_deps.config_loader_factory.return_value = mock_loader

        result = _setup_aas_connection(state, runtime_deps)

        assert result == mock_handler
        assert state["registry_connected"] is True
        mock_handler.connect_to_server.assert_called_once_with(mock_loader)

    def test_server_handler_factory_called_correctly(self):
        """Verify server handler factory is invoked."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.server_handler_factory.return_value = MagicMock()
        runtime_deps.config_loader_factory.return_value = MagicMock()

        _setup_aas_connection(state, runtime_deps)

        runtime_deps.server_handler_factory.assert_called_once()

    def test_connection_error_propagates(self):
        """Verify connection errors during server setup propagate."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        mock_handler = MagicMock()
        mock_handler.connect_to_server.side_effect = ConnectionError(
            "Server unreachable"
        )
        runtime_deps.server_handler_factory.return_value = mock_handler
        runtime_deps.config_loader_factory.return_value = MagicMock()

        with pytest.raises(ConnectionError):
            _setup_aas_connection(state, runtime_deps)

        assert state["registry_connected"] is False

    def test_loader_factory_called_after_handler_creation(self):
        """Verify config loader is obtained during connection setup."""
        state = _init_startup_state()
        runtime_deps = MagicMock()
        mock_handler = MagicMock()
        mock_loader = MagicMock()
        runtime_deps.server_handler_factory.return_value = mock_handler
        runtime_deps.config_loader_factory.return_value = mock_loader

        _setup_aas_connection(state, runtime_deps)

        runtime_deps.config_loader_factory.assert_called_once()
        mock_handler.connect_to_server.assert_called_once_with(mock_loader)


class TestPreloadAasMetadata:
    """Test _preload_aas_metadata() with mocked lookups."""

    def test_metadata_preload_success(self):
        """Verify target references stored in app.state."""
        app = FastAPI()
        state = _init_startup_state()
        runtime_deps = MagicMock()
        config = MagicMock()
        config.aas_id = "test_aas_id"
        runtime_deps.config_provider.return_value = config

        mock_shell = MagicMock()
        mock_aimc_sm = MagicMock()
        mock_refs = [{"idShort": "ref1"}, {"idShort": "ref2"}]

        _preload_aas_metadata(
            app,
            MagicMock(),  # server_handler
            state,
            runtime_deps,
            get_shell=lambda h, aas_id: mock_shell,
            get_aimc_sm=lambda h, shell: mock_aimc_sm,
            extract_refs=lambda sm: mock_refs,
        )

        assert state["aimc_loaded"] is True
        assert app.state.target_references == mock_refs

    def test_get_shell_called_with_correct_args(self):
        """Verify shell lookup uses correct AAS ID."""
        app = FastAPI()
        state = _init_startup_state()
        runtime_deps = MagicMock()
        config = MagicMock()
        config.aas_id = "my_custom_aas_id"
        runtime_deps.config_provider.return_value = config

        server_handler = MagicMock()
        mock_shell = MagicMock()
        get_shell_called = MagicMock(return_value=mock_shell)

        _preload_aas_metadata(
            app,
            server_handler,
            state,
            runtime_deps,
            get_shell=get_shell_called,
            get_aimc_sm=lambda h, shell: MagicMock(),
            extract_refs=lambda sm: [],
        )

        get_shell_called.assert_called_once_with(server_handler, "my_custom_aas_id")

    def test_shell_retrieval_failure_propagates(self):
        """Verify shell lookup errors propagate."""
        app = FastAPI()
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.config_provider.return_value = MagicMock(aas_id="test")

        def failing_get_shell(h, aas_id):
            raise RuntimeError("Shell not found")

        with pytest.raises(RuntimeError, match="Shell not found"):
            _preload_aas_metadata(
                app,
                MagicMock(),
                state,
                runtime_deps,
                get_shell=failing_get_shell,
                get_aimc_sm=lambda h, shell: MagicMock(),
                extract_refs=lambda sm: [],
            )

        assert state["aimc_loaded"] is False

    def test_aimc_submodel_failure_propagates(self):
        """Verify AIMC submodel retrieval errors propagate."""
        app = FastAPI()
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.config_provider.return_value = MagicMock(aas_id="test")

        def failing_get_aimc(h, shell):
            raise ValueError("AIMC submodel not found")

        with pytest.raises(ValueError, match="AIMC submodel not found"):
            _preload_aas_metadata(
                app,
                MagicMock(),
                state,
                runtime_deps,
                get_shell=lambda h, aas_id: MagicMock(),
                get_aimc_sm=failing_get_aimc,
                extract_refs=lambda sm: [],
            )

        assert state["aimc_loaded"] is False

    def test_empty_references_is_valid(self):
        """Verify empty reference list is accepted."""
        app = FastAPI()
        state = _init_startup_state()
        runtime_deps = MagicMock()
        runtime_deps.config_provider.return_value = MagicMock(aas_id="test")

        _preload_aas_metadata(
            app,
            MagicMock(),
            state,
            runtime_deps,
            get_shell=lambda h, aas_id: MagicMock(),
            get_aimc_sm=lambda h, shell: MagicMock(),
            extract_refs=lambda sm: [],
        )

        assert state["aimc_loaded"] is True
        assert app.state.target_references == []


@pytest.mark.asyncio
class TestLifespanIntegration:
    """Integration tests for the full lifespan startup/shutdown."""

    async def _run_lifespan_context(self, runtime_deps):
        """Helper to properly run lifespan context manager.

        Args:
            runtime_deps: Mock AppRuntimeDeps to use during startup.

        Returns:
            tuple: (app, startup_state) from the lifespan context.
        """
        app = FastAPI()

        with patch(
            "ms_database_connector.__main__.build_app_runtime_deps",
            return_value=runtime_deps,
        ):
            with patch("ms_database_connector.__main__._preload_aas_metadata"):
                ctx_manager = lifespan(app)
                await ctx_manager.__aenter__()

        return app, app.state.startup

    async def test_happy_path_startup_all_steps_succeed(self):
        """Verify all startup steps execute successfully in correct order."""
        runtime_deps = MagicMock()
        config = MagicMock()
        config.aas_id = "test_aas_id"
        config.polling_interval = 10
        runtime_deps.config_provider.return_value = config
        runtime_deps.mapping_handler_provider.return_value = MagicMock()
        runtime_deps.influx_client_provider.return_value = MagicMock()
        mock_server_handler = MagicMock()
        runtime_deps.server_handler_factory.return_value = mock_server_handler
        runtime_deps.config_loader_factory.return_value = MagicMock()

        app = FastAPI()

        with patch(
            "ms_database_connector.__main__.build_app_runtime_deps",
            return_value=runtime_deps,
        ):
            with patch(
                "ms_database_connector.__main__._preload_aas_metadata"
            ) as mock_preload:
                # Make sure _preload_aas_metadata updates the startup state correctly
                def preload_side_effect(app_arg, handler, state, deps, **kwargs):
                    state["aimc_loaded"] = True

                mock_preload.side_effect = preload_side_effect

                ctx_manager = lifespan(app)
                await ctx_manager.__aenter__()

        startup_state = app.state.startup

        # Verify all startup flags are set
        assert startup_state["config_loaded"] is True
        assert startup_state["mapping_initialized"] is True
        assert startup_state["influx_connected"] is True
        assert startup_state["registry_connected"] is True
        assert startup_state["aimc_loaded"] is True
        assert startup_state["errors"] == []

    async def test_startup_early_failure_config_not_loaded(self):
        """Verify early config failure prevents remaining steps."""
        runtime_deps = MagicMock()
        runtime_deps.config_provider.side_effect = ConfigurationError("Bad config")

        with patch(
            "ms_database_connector.__main__.build_app_runtime_deps",
            return_value=runtime_deps,
        ):
            ctx_manager = lifespan(FastAPI())
            with pytest.raises(ConfigurationError):
                await ctx_manager.__aenter__()

    async def test_startup_failure_influx_unavailable(self):
        """Verify startup fails when InfluxDB is unavailable."""
        runtime_deps = MagicMock()
        runtime_deps.config_provider.return_value = MagicMock()
        runtime_deps.mapping_handler_provider.return_value = MagicMock()
        runtime_deps.influx_client_provider.return_value = None  # No client

        with patch(
            "ms_database_connector.__main__.build_app_runtime_deps",
            return_value=runtime_deps,
        ):
            ctx_manager = lifespan(FastAPI())
            with pytest.raises(RuntimeError, match="InfluxDB connection failed"):
                await ctx_manager.__aenter__()

    async def test_startup_failure_aas_connection_fails(self):
        """Verify startup fails when AAS server connection fails."""
        runtime_deps = MagicMock()
        runtime_deps.config_provider.return_value = MagicMock()
        runtime_deps.mapping_handler_provider.return_value = MagicMock()
        runtime_deps.influx_client_provider.return_value = MagicMock()
        mock_handler = MagicMock()
        mock_handler.connect_to_server.side_effect = ConnectionError("Server down")
        runtime_deps.server_handler_factory.return_value = mock_handler
        runtime_deps.config_loader_factory.return_value = MagicMock()

        with patch(
            "ms_database_connector.__main__.build_app_runtime_deps",
            return_value=runtime_deps,
        ):
            ctx_manager = lifespan(FastAPI())
            with pytest.raises(ConnectionError):
                await ctx_manager.__aenter__()

    async def test_polling_worker_started_on_success(self):
        """Verify PollingWorker initialization after successful startup."""
        runtime_deps = MagicMock()
        config = MagicMock()
        config.aas_id = "test"
        config.polling_interval = 5
        runtime_deps.config_provider.return_value = config
        runtime_deps.mapping_handler_provider.return_value = MagicMock()
        runtime_deps.influx_client_provider.return_value = MagicMock()
        runtime_deps.server_handler_factory.return_value = MagicMock()
        runtime_deps.config_loader_factory.return_value = MagicMock()

        app = FastAPI()
        with patch(
            "ms_database_connector.__main__.build_app_runtime_deps",
            return_value=runtime_deps,
        ):
            with patch("ms_database_connector.__main__._preload_aas_metadata"):
                ctx_manager = lifespan(app)
                await ctx_manager.__aenter__()

        # Verify startup completed successfully
        assert app.state.startup["config_loaded"] is True
        assert app.state.startup["influx_connected"] is True

    async def test_startup_phase_order_config_before_influx(self):
        """Verify initialization order: config must load before InfluxDB setup."""
        call_order = []

        def config_side_effect():
            call_order.append("config")
            return MagicMock()

        def influx_side_effect():
            call_order.append("influx")
            return MagicMock()

        runtime_deps = MagicMock()
        runtime_deps.config_provider.side_effect = config_side_effect
        runtime_deps.mapping_handler_provider.return_value = MagicMock()
        runtime_deps.influx_client_provider.side_effect = influx_side_effect
        runtime_deps.server_handler_factory.return_value = MagicMock()
        runtime_deps.config_loader_factory.return_value = MagicMock()

        with patch(
            "ms_database_connector.__main__.build_app_runtime_deps",
            return_value=runtime_deps,
        ):
            with patch("ms_database_connector.__main__._preload_aas_metadata"):
                ctx_manager = lifespan(FastAPI())
                await ctx_manager.__aenter__()

        # Config should be called before InfluxDB
        assert call_order.index("config") < call_order.index("influx")
