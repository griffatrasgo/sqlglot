import unittest

from sqlglot import exp, parse_one, to_table
from sqlglot.errors import SchemaError
from sqlglot.schema import MappingSchema, ensure_schema


class TestSchema(unittest.TestCase):
    def assert_column_names(self, schema, *table_results):
        for table, result in table_results:
            with self.subTest(f"{table} -> {result}"):
                self.assertEqual(schema.column_names(to_table(table)), result)

    def assert_column_names_raises(self, schema, *tables):
        for table in tables:
            with self.subTest(table):
                with self.assertRaises(SchemaError):
                    schema.column_names(to_table(table))

    def test_schema(self):
        schema = ensure_schema(
            {
                "x": {
                    "a": "uint64",
                },
                "y": {
                    "b": "uint64",
                    "c": "uint64",
                },
            },
        )

        self.assert_column_names(
            schema,
            ("x", ["a"]),
            ("y", ["b", "c"]),
            ("z.x", ["a"]),
            ("z.x.y", ["b", "c"]),
        )

        self.assert_column_names_raises(
            schema,
            "z",
            "z.z",
            "z.z.z",
        )

    def test_schema_db(self):
        schema = ensure_schema(
            {
                "d1": {
                    "x": {
                        "a": "uint64",
                    },
                    "y": {
                        "b": "uint64",
                    },
                },
                "d2": {
                    "x": {
                        "c": "uint64",
                    },
                },
            },
        )

        self.assert_column_names(
            schema,
            ("d1.x", ["a"]),
            ("d2.x", ["c"]),
            ("y", ["b"]),
            ("d1.y", ["b"]),
            ("z.d1.y", ["b"]),
        )

        self.assert_column_names_raises(
            schema,
            "x",
            "z.x",
            "z.y",
        )

    def test_schema_catalog(self):
        schema = ensure_schema(
            {
                "c1": {
                    "d1": {
                        "x": {
                            "a": "uint64",
                        },
                        "y": {
                            "b": "uint64",
                        },
                        "z": {
                            "c": "uint64",
                        },
                    },
                },
                "c2": {
                    "d1": {
                        "y": {
                            "d": "uint64",
                        },
                        "z": {
                            "e": "uint64",
                        },
                    },
                    "d2": {
                        "z": {
                            "f": "uint64",
                        },
                    },
                },
            }
        )

        self.assert_column_names(
            schema,
            ("x", ["a"]),
            ("d1.x", ["a"]),
            ("c1.d1.x", ["a"]),
            ("c1.d1.y", ["b"]),
            ("c1.d1.z", ["c"]),
            ("c2.d1.y", ["d"]),
            ("c2.d1.z", ["e"]),
            ("d2.z", ["f"]),
            ("c2.d2.z", ["f"]),
        )

        self.assert_column_names_raises(
            schema,
            "q",
            "d2.x",
            "y",
            "z",
            "d1.y",
            "d1.z",
            "a.b.c",
        )

    def test_schema_add_table_with_and_without_mapping(self):
        schema = MappingSchema()
        schema.add_table("test")
        self.assertEqual(schema.column_names("test"), [])
        schema.add_table("test", {"x": "string"})
        self.assertEqual(schema.column_names("test"), ["x"])
        schema.add_table("test", {"x": "string", "y": "int"})
        self.assertEqual(schema.column_names("test"), ["x", "y"])
        schema.add_table("test")
        self.assertEqual(schema.column_names("test"), ["x", "y"])

    def test_schema_get_column_type(self):
        schema = MappingSchema({"a": {"b": "varchar"}})
        self.assertEqual(schema.get_column_type("a", "b").this, exp.DataType.Type.VARCHAR)
        self.assertEqual(
            schema.get_column_type(exp.Table(this="a"), exp.Column(this="b")).this,
            exp.DataType.Type.VARCHAR,
        )
        self.assertEqual(
            schema.get_column_type("a", exp.Column(this="b")).this, exp.DataType.Type.VARCHAR
        )
        self.assertEqual(
            schema.get_column_type(exp.Table(this="a"), "b").this, exp.DataType.Type.VARCHAR
        )
        schema = MappingSchema({"a": {"b": {"c": "varchar"}}})
        self.assertEqual(
            schema.get_column_type(exp.Table(this="b", db="a"), exp.Column(this="c")).this,
            exp.DataType.Type.VARCHAR,
        )
        self.assertEqual(
            schema.get_column_type(exp.Table(this="b", db="a"), "c").this, exp.DataType.Type.VARCHAR
        )
        schema = MappingSchema({"a": {"b": {"c": {"d": "varchar"}}}})
        self.assertEqual(
            schema.get_column_type(
                exp.Table(this="c", db="b", catalog="a"), exp.Column(this="d")
            ).this,
            exp.DataType.Type.VARCHAR,
        )
        self.assertEqual(
            schema.get_column_type(exp.Table(this="c", db="b", catalog="a"), "d").this,
            exp.DataType.Type.VARCHAR,
        )

        schema = MappingSchema({"foo": {"bar": parse_one("INT", into=exp.DataType)}})
        self.assertEqual(schema.get_column_type("foo", "bar").this, exp.DataType.Type.INT)

    def test_schema_normalization(self):
        schema = MappingSchema(
            schema={"x": {"`y`": {"Z": {"a": "INT", "`B`": "VARCHAR"}, "w": {"C": "INT"}}}},
            dialect="spark",
        )

        table_z = exp.Table(this="z", db="y", catalog="x")
        table_w = exp.Table(this="w", db="y", catalog="x")

        self.assertEqual(schema.column_names(table_z), ["a", "B"])
        self.assertEqual(schema.column_names(table_w), ["c"])

        # Clickhouse supports both `` and "" for identifier quotes; sqlglot uses "" when generating sql
        schema = MappingSchema(schema={"x": {"`y`": "INT"}}, dialect="clickhouse")
        self.assertEqual(schema.column_names(exp.Table(this="x")), ["y"])
