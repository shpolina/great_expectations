import enum
import os
import shutil
import subprocess
import sys

import pytest

from assets.scripts.build_gallery import execute_shell_command
from great_expectations.data_context.util import file_relative_path


class BackendDependencies(enum.Enum):
    MYSQL = "MYSQL"
    MSSQL = "MSSQL"
    PANDAS = "PANDAS"
    POSTGRESQL = "POSTGRESQL"
    SPARK = "SPARK"
    SQLALCHEMY = "SQLALCHEMY"


def get_database_csv_loader(
    table_name: str, file_relative_csv_path: str, connection_string: str
):
    absolute_csv_path = os.path.abspath(
        file_relative_path(__file__, file_relative_csv_path)
    )

    def _load_data():
        import pandas as pd
        import sqlalchemy as sa

        engine = sa.create_engine(connection_string)
        engine.execute(f"DROP TABLE IF EXISTS {table_name}")
        print(f"Dropping table {table_name}")
        df = pd.read_csv(absolute_csv_path)
        print(f"Creating table {table_name} from {absolute_csv_path}")
        df.to_sql(name=table_name, con=engine, index=False)

    return _load_data


docs_test_matrix = [
    {
        "user_flow_script": "tests/integration/docusaurus/connecting_to_your_data/filesystem/pandas_yaml_example.py",
        "base_dir": file_relative_path(__file__, "../../"),
        "data_context_dir": "tests/integration/fixtures/no_datasources/great_expectations",
        "data_dir": "tests/test_sets/taxi_yellow_trip_data_samples",
    },
    {
        "user_flow_script": "tests/integration/docusaurus/connecting_to_your_data/filesystem/pandas_python_example.py",
        "base_dir": file_relative_path(__file__, "../../"),
        "data_context_dir": "tests/integration/fixtures/no_datasources/great_expectations",
        "data_dir": "tests/test_sets/taxi_yellow_trip_data_samples",
    },
    {
        "user_flow_script": "tests/integration/docusaurus/connecting_to_your_data/database/postgres_yaml_example.py",
        "base_dir": file_relative_path(__file__, "../../"),
        "data_context_dir": "tests/integration/fixtures/no_datasources/great_expectations",
        "extra_backend_dependencies": BackendDependencies.POSTGRESQL,
        "data_setup_callable": get_database_csv_loader(
            table_name="taxi_data",
            file_relative_csv_path="../test_sets/taxi_yellow_trip_data_samples/yellow_trip_data_sample_2019-01.csv",
            connection_string="postgresql+psycopg2://postgres:@localhost/test_ci",
        ),
    },
    {
        "user_flow_script": "tests/integration/docusaurus/connecting_to_your_data/database/postgres_python_example.py",
        "base_dir": file_relative_path(__file__, "../../"),
        "data_context_dir": "tests/integration/fixtures/no_datasources/great_expectations",
        "extra_backend_dependencies": BackendDependencies.POSTGRESQL,
        "data_setup_callable": get_database_csv_loader(
            table_name="taxi_data",
            file_relative_csv_path="../test_sets/taxi_yellow_trip_data_samples/yellow_trip_data_sample_2019-01.csv",
            connection_string="postgresql+psycopg2://postgres:@localhost/test_ci",
        ),
    },
]

integration_test_matrix = [
    {
        "name": "pandas_one_multi_batch_request_one_validator",
        "base_dir": file_relative_path(__file__, "../../"),
        "data_context_dir": "tests/integration/fixtures/yellow_trip_data_pandas_fixture/great_expectations",
        "data_dir": "tests/test_sets/taxi_yellow_trip_data_samples",
        "user_flow_script": "tests/integration/fixtures/yellow_trip_data_pandas_fixture/one_multi_batch_request_one_validator.py",
    },
    {
        "name": "pandas_two_batch_requests_two_validators",
        "base_dir": file_relative_path(__file__, "../../"),
        "data_context_dir": "tests/integration/fixtures/yellow_trip_data_pandas_fixture/great_expectations",
        "data_dir": "tests/test_sets/taxi_yellow_trip_data_samples",
        "user_flow_script": "tests/integration/fixtures/yellow_trip_data_pandas_fixture/two_batch_requests_two_validators.py",
        "expected_stderrs": "",
        "expected_stdouts": "",
    },
    {
        "name": "pandas_multiple_batch_requests_one_validator_multiple_steps",
        "base_dir": file_relative_path(__file__, "../../"),
        "data_context_dir": "tests/integration/fixtures/yellow_trip_data_pandas_fixture/great_expectations",
        "data_dir": "tests/test_sets/taxi_yellow_trip_data_samples",
        "user_flow_script": "tests/integration/fixtures/yellow_trip_data_pandas_fixture/multiple_batch_requests_one_validator_multiple_steps.py",
    },
    {
        "name": "pandas_multiple_batch_requests_one_validator_one_step",
        "base_dir": file_relative_path(__file__, "../../"),
        "data_context_dir": "tests/integration/fixtures/yellow_trip_data_pandas_fixture/great_expectations",
        "data_dir": "tests/test_sets/taxi_yellow_trip_data_samples",
        "user_flow_script": "tests/integration/fixtures/yellow_trip_data_pandas_fixture/multiple_batch_requests_one_validator_one_step.py",
    },
]


def idfn(test_configuration):
    return test_configuration.get("user_flow_script")


@pytest.fixture
def pytest_parsed_arguments(request):
    return request.config.option


@pytest.mark.docs
@pytest.mark.integration
@pytest.mark.parametrize("test_configuration", docs_test_matrix, ids=idfn)
@pytest.mark.skipif(sys.version_info < (3, 7), reason="requires Python3.7")
def test_docs(test_configuration, tmp_path, pytest_parsed_arguments):
    _check_for_skipped_tests(pytest_parsed_arguments, test_configuration)
    _execute_integration_test(test_configuration, tmp_path)


@pytest.mark.integration
@pytest.mark.parametrize("test_configuration", integration_test_matrix, ids=idfn)
@pytest.mark.skipif(sys.version_info < (3, 7), reason="requires Python3.7")
def test_integration_tests(test_configuration, tmp_path, pytest_parsed_arguments):
    _check_for_skipped_tests(pytest_parsed_arguments, test_configuration)
    _execute_integration_test(test_configuration, tmp_path)


def _execute_integration_test(test_configuration, tmp_path):
    """
    Prepare and environment and run integration tests.
    """
    workdir = os.getcwd()
    try:
        os.chdir(tmp_path)
        base_dir = test_configuration.get("base_dir", ".")
        # Ensure GE is installed in our environment
        ge_requirement = test_configuration.get("ge_requirement", "great_expectations")
        execute_shell_command(f"pip install {ge_requirement}")

        #
        # Build test state
        #

        # DataContext
        context_source_dir = os.path.join(
            base_dir, test_configuration.get("data_context_dir")
        )
        test_context_dir = os.path.join(tmp_path, "great_expectations")
        shutil.copytree(
            context_source_dir,
            test_context_dir,
        )

        # Test Data
        if test_configuration.get("data_dir") is not None:
            source_data_dir = os.path.join(base_dir, test_configuration.get("data_dir"))
            test_data_dir = os.path.join(tmp_path, "data")
            shutil.copytree(
                source_data_dir,
                test_data_dir,
            )

        db_setup_function = test_configuration.get("data_setup_callable")
        if db_setup_function is not None:
            db_setup_function()

        # UAT Script
        script_source = os.path.join(
            test_configuration.get("base_dir"),
            test_configuration.get("user_flow_script"),
        )
        script_path = os.path.join(tmp_path, "test_script.py")
        shutil.copyfile(script_source, script_path)
        # Check initial state

        # Execute test
        res = subprocess.run(["python", script_path], capture_output=True)
        # Check final state
        expected_stderrs = test_configuration.get("expected_stderrs")
        expected_stdouts = test_configuration.get("expected_stdouts")
        expected_failure = test_configuration.get("expected_failure")
        outs = res.stdout.decode("utf-8")
        errs = res.stderr.decode("utf-8")
        print(outs)
        print(errs)

        if expected_stderrs:
            assert expected_stderrs == errs

        if expected_stdouts:
            assert expected_stdouts == outs

        if expected_failure:
            assert res.returncode != 0
        else:
            assert res.returncode == 0
    except:
        raise
    finally:
        os.chdir(workdir)


def _check_for_skipped_tests(pytest_args, test_configuration) -> None:
    """Enable scripts to be skipped based on pytest invocation flags."""
    dependencies = test_configuration.get("extra_backend_dependencies", None)
    if not dependencies:
        return
    elif dependencies == BackendDependencies.POSTGRESQL and (
        pytest_args.no_postgresql or pytest_args.no_sqlalchemy
    ):
        pytest.skip("Skipping postgres tests")
    elif dependencies == BackendDependencies.MYSQL and (
        pytest_args.no_mysql or pytest_args.no_sqlalchemy
    ):
        pytest.skip("Skipping mysql tests")
    elif dependencies == BackendDependencies.MSSQL and (
        pytest_args.no_mssql or pytest_args.no_sqlalchemy
    ):
        pytest.skip("Skipping mssql tests")
    elif dependencies == BackendDependencies.SPARK and pytest_args.no_spark:
        pytest.skip("Skipping spark tests")
