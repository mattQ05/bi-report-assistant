from pathlib import Path
import os
import sys
import clr


# ============================================================
# ADOMD.NET setup
# ============================================================
ADOMD_DLL_PATH = os.getenv(
    "ADOMD_DLL_PATH",
    r"C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.AdomdClient.dll"
)
dll_path = Path(ADOMD_DLL_PATH)

if not dll_path.exists():
    raise FileNotFoundError(
        f"Could not find ADOMD.NET DLL at:\n{ADOMD_DLL_PATH}\n\n"
        "Search for Microsoft.AnalysisServices.AdomdClient.dll on your computer "
        "and update ADOMD_DLL_PATH."
    )

adomd_folder = str(dll_path.parent)
os.environ["PATH"] = adomd_folder + os.pathsep + os.environ["PATH"]

if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(adomd_folder)

sys.path.append(adomd_folder)
clr.AddReference(str(dll_path))

from Microsoft.AnalysisServices.AdomdClient import AdomdConnection


# ============================================================
# File helpers
# ============================================================
PROJECT_FOLDER = Path(__file__).resolve().parent
POWERBI_CONTEXT_FILE = PROJECT_FOLDER / "powerbi_context.txt"
OUTPUT_FILE = PROJECT_FOLDER / "powerbi_model_context.txt"


def read_powerbi_context_file() -> tuple[str, str]:
    if not POWERBI_CONTEXT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find powerbi_context.txt at: {POWERBI_CONTEXT_FILE}\n"
            "Open Power BI Desktop, click your BI Report Assistant external tool, then try again."
        )

    text = POWERBI_CONTEXT_FILE.read_text(encoding="utf-8")

    server = ""
    database = ""

    lines = [line.strip() for line in text.splitlines()]

    for index, line in enumerate(lines):
        if line.lower() == "server:" and index + 1 < len(lines):
            server = lines[index + 1].strip()

        if line.lower() == "database:" and index + 1 < len(lines):
            database = lines[index + 1].strip()

    if not server or not database:
        raise ValueError("Could not find Server and Database values inside powerbi_context.txt.")

    return server, database


# ============================================================
# Query helpers
# ============================================================
def run_dmv_query(connection: AdomdConnection, query: str) -> list[dict]:
    command = connection.CreateCommand()
    command.CommandText = query

    reader = command.ExecuteReader()
    rows = []

    try:
        field_names = [reader.GetName(i) for i in range(reader.FieldCount)]

        while reader.Read():
            row = {}
            for i, field_name in enumerate(field_names):
                value = reader.GetValue(i)
                row[field_name] = None if value is None else value
            rows.append(row)

    finally:
        reader.Close()

    return rows


def get_value(row: dict, *possible_names, default=""):
    for name in possible_names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def is_truthy(value) -> bool:
    return str(value).lower() in ["true", "1", "yes"]


# ============================================================
# Metadata extraction
# ============================================================
def extract_metadata() -> str:
    server, database = read_powerbi_context_file()

    connection_string = (
        f"Provider=MSOLAP;"
        f"Data Source={server};"
        f"Initial Catalog={database};"
    )

    connection = AdomdConnection(connection_string)

    try:
        connection.Open()

        tables = run_dmv_query(connection, "SELECT * FROM $SYSTEM.TMSCHEMA_TABLES")
        columns = run_dmv_query(connection, "SELECT * FROM $SYSTEM.TMSCHEMA_COLUMNS")
        measures = run_dmv_query(connection, "SELECT * FROM $SYSTEM.TMSCHEMA_MEASURES")
        relationships = run_dmv_query(connection, "SELECT * FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS")

    finally:
        connection.Close()

    table_by_id = {}
    visible_tables = []

    for table in tables:
        table_id = get_value(table, "ID", "TableID")
        table_name = get_value(table, "Name")
        is_hidden = is_truthy(get_value(table, "IsHidden", default=False))

        if table_id:
            table_by_id[str(table_id)] = table_name

        if not is_hidden:
            visible_tables.append(table)

    column_by_id = {}
    visible_columns = []

    for column in columns:
        column_id = get_value(column, "ID", "ColumnID")
        table_id = get_value(column, "TableID")
        column_name = get_value(column, "ExplicitName", "Name", "InferredName")
        is_hidden = is_truthy(get_value(column, "IsHidden", default=False))
        table_name = table_by_id.get(str(table_id), f"UnknownTable_{table_id}")

        if column_id:
            column_by_id[str(column_id)] = {
                "table": table_name,
                "column": column_name,
            }

        if not is_hidden and table_name in [get_value(t, "Name") for t in visible_tables]:
            visible_columns.append(column)

    lines = []

    lines.append("# Power BI Model Context")
    lines.append("")
    lines.append("This file was automatically extracted from the currently open Power BI Desktop model.")
    lines.append("")
    lines.append("## Connection")
    lines.append(f"- Server: {server}")
    lines.append(f"- Database: {database}")
    lines.append("")

    # Tables
    lines.append("## Tables")
    lines.append("")

    for table in visible_tables:
        table_name = get_value(table, "Name")
        table_description = get_value(table, "Description")

        lines.append(f"### Table: {table_name}")

        if table_description:
            lines.append(f"Description: {table_description}")

        lines.append("")

    # Columns grouped by table
    lines.append("## Columns")
    lines.append("")

    visible_table_names = [get_value(t, "Name") for t in visible_tables]

    for table_name in visible_table_names:
        lines.append(f"### {table_name}")
        table_columns = []

        for column in visible_columns:
            table_id = get_value(column, "TableID")
            column_table_name = table_by_id.get(str(table_id), "")

            if column_table_name == table_name:
                column_name = get_value(column, "ExplicitName", "Name", "InferredName")
                data_type = get_value(column, "DataType", "ExplicitDataType", "InferredDataType")
                column_type = get_value(column, "Type", "ColumnType")
                expression = get_value(column, "Expression")

                table_columns.append(
                    {
                        "name": column_name,
                        "data_type": data_type,
                        "column_type": column_type,
                        "expression": expression,
                    }
                )

        if not table_columns:
            lines.append("- No visible columns found.")
        else:
            for col in table_columns:
                line = f"- {table_name}[{col['name']}]"
                if col["data_type"]:
                    line += f" | DataType: {col['data_type']}"
                if col["column_type"]:
                    line += f" | ColumnType: {col['column_type']}"
                lines.append(line)

                if col["expression"]:
                    lines.append("  ```DAX")
                    lines.append(f"  {col['expression']}")
                    lines.append("  ```")

        lines.append("")

    # Measures
    lines.append("## Measures")
    lines.append("")

    visible_measures = []

    for measure in measures:
        table_id = get_value(measure, "TableID")
        table_name = table_by_id.get(str(table_id), f"UnknownTable_{table_id}")
        measure_name = get_value(measure, "Name")
        expression = get_value(measure, "Expression")
        description = get_value(measure, "Description")
        is_hidden = is_truthy(get_value(measure, "IsHidden", default=False))

        if is_hidden:
            continue

        visible_measures.append(measure)

        lines.append(f"### {measure_name}")
        lines.append(f"Table: {table_name}")

        if description:
            lines.append(f"Description: {description}")

        lines.append("")
        lines.append("```DAX")
        lines.append(f"{measure_name} =")
        lines.append(str(expression).strip() if expression else "-- No expression found")
        lines.append("```")
        lines.append("")

    if not visible_measures:
        lines.append("No visible measures found.")
        lines.append("")

    # Relationships
    lines.append("## Relationships")
    lines.append("")

    visible_relationship_count = 0

    for relationship in relationships:
        from_table_id = get_value(relationship, "FromTableID")
        from_column_id = get_value(relationship, "FromColumnID")
        to_table_id = get_value(relationship, "ToTableID")
        to_column_id = get_value(relationship, "ToColumnID")
        is_active = get_value(relationship, "IsActive")
        cross_filtering = get_value(relationship, "CrossFilteringBehavior")
        relationship_name = get_value(relationship, "Name")

        from_table = table_by_id.get(str(from_table_id), "")
        to_table = table_by_id.get(str(to_table_id), "")

        from_column = column_by_id.get(str(from_column_id), {})
        to_column = column_by_id.get(str(to_column_id), {})

        if from_table not in visible_table_names or to_table not in visible_table_names:
            continue

        visible_relationship_count += 1

        from_col_name = from_column.get("column", f"ColumnID_{from_column_id}")
        to_col_name = to_column.get("column", f"ColumnID_{to_column_id}")

        line = f"- {from_table}[{from_col_name}] → {to_table}[{to_col_name}]"

        if relationship_name:
            line += f" | Name: {relationship_name}"

        if is_active != "":
            line += f" | Active: {is_active}"

        if cross_filtering != "":
            line += f" | CrossFiltering: {cross_filtering}"

        lines.append(line)

    if visible_relationship_count == 0:
        lines.append("No visible relationships found.")

    lines.append("")

    # Hidden object summary
    hidden_tables_count = len(tables) - len(visible_tables)
    hidden_columns_count = len(columns) - len(visible_columns)
    hidden_measures_count = len(measures) - len(visible_measures)

    lines.append("## Hidden Object Summary")
    lines.append(f"- Hidden tables skipped: {hidden_tables_count}")
    lines.append(f"- Hidden columns skipped: {hidden_columns_count}")
    lines.append(f"- Hidden measures skipped: {hidden_measures_count}")
    lines.append("")
    lines.append("Note: Power BI may create hidden date tables automatically. These are usually skipped to keep the assistant context cleaner.")

    return "\n".join(lines)


def main() -> None:
    print("Extracting Power BI model metadata...")

    metadata_text = extract_metadata()
    OUTPUT_FILE.write_text(metadata_text, encoding="utf-8")

    print(f"Metadata exported to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()