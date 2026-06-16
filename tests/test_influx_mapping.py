"""Unit tests for ms_database_connector.core.influx_mapping."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from ms_database_connector.config.db_mapping import DbMapping, MappingTargetType
from ms_database_connector.core.influx_mapping import (
    InfluxMapper,
    check_access_to_elements,
    extract_target_references_from_aimc,
    extract_target_references_from_mapping_configuration,
    get_aimc_submodel,
    get_mapping_configurations,
)
from ms_database_connector.models.influx_data import InfluxDataPoint


def _make_ref(submodel_id: str, parent_path: list[str], property_name: str):
    """Create a lightweight reference-like object for tests."""
    return SimpleNamespace(
        submodel_id=submodel_id,
        parent_path=parent_path,
        property_name=property_name,
    )


class TestGetAIMCSubmodel:
    def test_returns_matching_submodel(self):
        server_handler = object()
        shell = object()
        submodel_a = object()
        submodel_b = object()

        with (
            patch(
                "ms_database_connector.core.influx_mapping.aas_parser.get_submodel_ids",
                return_value=["sm-1", "sm-2"],
            ),
            patch(
                "ms_database_connector.core.influx_mapping.get_submodel_via_registry",
                side_effect=[submodel_a, submodel_b],
            ),
            patch(
                "ms_database_connector.core.influx_mapping.submodel_parser.get_semantic_id_value",
                side_effect=[
                    "/other/semantic",
                    "/idta/AssetInterfacesMappingConfiguration/v1",
                ],
            ),
        ):
            result = get_aimc_submodel(server_handler, shell)

        assert result is submodel_b

    def test_raises_not_found_when_no_matching_submodel(self):
        server_handler = object()
        shell = object()

        with (
            patch(
                "ms_database_connector.core.influx_mapping.aas_parser.get_submodel_ids",
                return_value=["sm-1"],
            ),
            patch(
                "ms_database_connector.core.influx_mapping.get_submodel_via_registry",
                return_value=object(),
            ),
            patch(
                "ms_database_connector.core.influx_mapping.submodel_parser.get_semantic_id_value",
                return_value="/something/else",
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                get_aimc_submodel(server_handler, shell)

        assert exc.value.status_code == 404


class TestMappingConfigurationHelpers:
    def test_get_mapping_configurations_returns_parsed_object(self):
        aimc_submodel = object()
        parsed = SimpleNamespace(configurations=[SimpleNamespace()])

        with patch(
            "ms_database_connector.core.influx_mapping.aimc_parser.parse_mapping_configurations",
            return_value=parsed,
        ):
            result = get_mapping_configurations(aimc_submodel)

        assert result is parsed

    @pytest.mark.parametrize("parsed", [None, SimpleNamespace(configurations=[])])
    def test_get_mapping_configurations_raises_on_empty_or_none(self, parsed):
        aimc_submodel = object()

        with patch(
            "ms_database_connector.core.influx_mapping.aimc_parser.parse_mapping_configurations",
            return_value=parsed,
        ):
            with pytest.raises(HTTPException) as exc:
                get_mapping_configurations(aimc_submodel)

        assert exc.value.status_code == 404

    def test_extract_target_references_from_mapping_configuration_flattens_relations(
        self,
    ):
        ref_a = _make_ref("sm-1", ["a"], "temp")
        ref_b = _make_ref("sm-2", ["b", "c"], "status")

        relation_a = SimpleNamespace(sink_properties=ref_a)
        relation_b = SimpleNamespace(sink_properties=ref_b)
        configuration = SimpleNamespace(
            source_sink_relations=[relation_a, relation_b],
            interface_reference=SimpleNamespace(value="if-ref"),
        )
        mapping_configurations = SimpleNamespace(configurations=[configuration])

        result = extract_target_references_from_mapping_configuration(
            mapping_configurations
        )

        assert result == [ref_a, ref_b]

    def test_extract_target_references_from_aimc_delegates(self):
        aimc_sm = object()
        mapping_configurations = SimpleNamespace(configurations=[SimpleNamespace()])
        refs = [_make_ref("sm-1", ["x"], "y")]

        with (
            patch(
                "ms_database_connector.core.influx_mapping.get_mapping_configurations",
                return_value=mapping_configurations,
            ) as get_configs,
            patch(
                "ms_database_connector.core.influx_mapping.extract_target_references_from_mapping_configuration",
                return_value=refs,
            ) as extract_refs,
        ):
            result = extract_target_references_from_aimc(aimc_sm)

        get_configs.assert_called_once_with(aimc_sm)
        extract_refs.assert_called_once_with(mapping_configurations)
        assert result == refs


class TestAccessCheck:
    def test_check_access_to_elements_true_when_all_accessible(self):
        server_handler = object()
        refs = [
            _make_ref("sm-1", ["motor"], "speed"),
            _make_ref("sm-2", ["meta", "state"], "code"),
        ]

        with patch(
            "ms_database_connector.core.influx_mapping.has_access_to_sme",
            side_effect=[True, True],
        ) as access_check:
            result = check_access_to_elements(server_handler, refs)

        assert result is True
        assert access_check.call_count == 2

    def test_check_access_to_elements_false_on_first_denied_access(self):
        server_handler = object()
        refs = [
            _make_ref("sm-1", ["motor"], "speed"),
            _make_ref("sm-2", ["meta"], "code"),
        ]

        with patch(
            "ms_database_connector.core.influx_mapping.has_access_to_sme",
            side_effect=[False, True],
        ) as access_check:
            result = check_access_to_elements(server_handler, refs)

        assert result is False
        # Stops early when first entry is denied.
        assert access_check.call_count == 1


class TestInfluxMapper:
    def test_map_smes_to_influx_builds_points_for_measurements_with_values(self):
        ref_speed = _make_ref("sm-1", ["motor"], "speed")
        ref_status = _make_ref("sm-1", ["motor"], "status")
        mapping = DbMapping.model_validate(
            {
                "motor_measurement": {
                    "sm-1/submodel-elements/motor.speed": "field",
                    "sm-1/submodel-elements/motor.status": "tag",
                },
                "empty_measurement": {
                    "sm-1/submodel-elements/motor.missing": "field",
                },
            }
        )
        mapper = InfluxMapper(
            server_handler=object(),
            db_mapping=mapping,
            target_references=[ref_speed, ref_status],
        )

        with (
            patch(
                "ms_database_connector.core.influx_mapping.check_access_to_elements",
                return_value=True,
            ),
            patch.object(
                mapper,
                "_retrieve_sme_value",
                side_effect=[123.4, "RUNNING"],
            ),
        ):
            result = mapper.map_smes_to_influx()

        assert set(result.keys()) == {"motor_measurement"}
        point = result["motor_measurement"][0]
        assert point.fields["sm-1/submodel-elements/motor.speed"] == 123.4
        assert point.tags["sm-1/submodel-elements/motor.status"] == "RUNNING"

    def test_map_smes_to_influx_raises_bad_request_when_access_fails(self):
        mapping = DbMapping.model_validate(
            {"m": {"sm-1/submodel-elements/a.b": "field"}}
        )
        mapper = InfluxMapper(
            server_handler=object(),
            db_mapping=mapping,
            target_references=[_make_ref("sm-1", ["a"], "b")],
        )

        with patch(
            "ms_database_connector.core.influx_mapping.check_access_to_elements",
            return_value=False,
        ):
            with pytest.raises(HTTPException) as exc:
                mapper.map_smes_to_influx()

        assert exc.value.status_code == 400

    def test_retrieve_sme_value_returns_none_when_element_missing(self):
        mapper = InfluxMapper(
            server_handler=object(),
            db_mapping=DbMapping.model_validate({}),
            target_references=[],
        )
        ref = _make_ref("sm-1", ["a"], "b")

        with (
            patch(
                "ms_database_connector.core.influx_mapping.get_submodel_via_registry",
                return_value=object(),
            ),
            patch(
                "ms_database_connector.core.influx_mapping.submodel_parser.get_submodel_element_by_id_short_path",
                return_value=None,
            ),
        ):
            result = mapper._retrieve_sme_value(ref)

        assert result is None

    def test_retrieve_sme_value_returns_none_when_sme_has_no_value(self):
        mapper = InfluxMapper(
            server_handler=object(),
            db_mapping=DbMapping.model_validate({}),
            target_references=[],
        )
        ref = _make_ref("sm-1", ["a"], "b")

        with (
            patch(
                "ms_database_connector.core.influx_mapping.get_submodel_via_registry",
                return_value=object(),
            ),
            patch(
                "ms_database_connector.core.influx_mapping.submodel_parser.get_submodel_element_by_id_short_path",
                return_value=object(),
            ),
        ):
            result = mapper._retrieve_sme_value(ref)

        assert result is None

    def test_retrieve_sme_value_returns_sme_value(self):
        mapper = InfluxMapper(
            server_handler=object(),
            db_mapping=DbMapping.model_validate({}),
            target_references=[],
        )
        ref = _make_ref("sm-1", ["a"], "b")
        sme = SimpleNamespace(value=42)

        with (
            patch(
                "ms_database_connector.core.influx_mapping.get_submodel_via_registry",
                return_value=object(),
            ),
            patch(
                "ms_database_connector.core.influx_mapping.submodel_parser.get_submodel_element_by_id_short_path",
                return_value=sme,
            ),
        ):
            result = mapper._retrieve_sme_value(ref)

        assert result == 42

    def test_add_value_to_point_returns_false_on_retrieve_exception(self):
        point = InfluxDataPoint(measurement="m")
        ref = _make_ref("sm-1", ["a"], "b")
        mapper = InfluxMapper(
            server_handler=object(),
            db_mapping=DbMapping.model_validate({}),
            target_references=[ref],
        )
        reference_map = {"sm-1/submodel-elements/a.b": ref}

        with patch.object(
            mapper,
            "_retrieve_sme_value",
            side_effect=RuntimeError("boom"),
        ):
            result = mapper._add_value_to_point(
                point,
                "sm-1/submodel-elements/a.b",
                MappingTargetType.FIELD,
                reference_map,
            )

        assert result is False
        assert point.fields == {}

    def test_convert_to_iso_timestamp_handles_supported_types(self):
        mapper = InfluxMapper(
            server_handler=object(),
            db_mapping=DbMapping.model_validate({}),
            target_references=[],
        )

        # ISO string with Z suffix.
        assert mapper._convert_to_iso_timestamp("2024-01-01T00:00:00Z").startswith(
            "2024-01-01T00:00:00"
        )

        # Datetime object.
        dt = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        assert mapper._convert_to_iso_timestamp(dt) == dt.isoformat()

        # Unix timestamp number.
        converted = mapper._convert_to_iso_timestamp(1704067200)
        assert converted.startswith("2024-01-01T00:00:00")

        # Unsupported type falls back to str().
        assert mapper._convert_to_iso_timestamp(object()).startswith("<object object")
