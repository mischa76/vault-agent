"""The DDL parser must read EVERY constraint of an `ALTER TABLE ... ADD` statement.

Found 2026-09-12 while auditing the WP30 rerun: instawdb.sql adds several constraints per
statement (`ADD CONSTRAINT [FK_a] ..., CONSTRAINT [FK_b] ..., CONSTRAINT [FK_c] ...;`), and the
old regex — anchored on `ALTER TABLE ... ADD CONSTRAINT` — captured only the first. 44 of the
90 foreign keys never reached the derived schemas, among them the second key of every
relationship table (`ProductVendor` → `Vendor`, `SpecialOfferProduct` → `SpecialOffer`). Every
WP34/WP36 measurement so far ran on that half of the evidence.
"""
from eval.adventureworks.extract import parse

_DDL = """
CREATE TABLE [Purchasing].[ProductVendor](
    [ProductID] [int] NOT NULL,
    [BusinessEntityID] [int] NOT NULL,
    [UnitMeasureCode] [nchar](3) NOT NULL
) ON [PRIMARY];
GO
ALTER TABLE [Purchasing].[ProductVendor] ADD
    CONSTRAINT [FK_ProductVendor_Product_ProductID] FOREIGN KEY
    (
        [ProductID]
    ) REFERENCES [Production].[Product](
        [ProductID]
    ),
    CONSTRAINT [FK_ProductVendor_UnitMeasure_UnitMeasureCode] FOREIGN KEY
    (
        [UnitMeasureCode]
    ) REFERENCES [Production].[UnitMeasure](
        [UnitMeasureCode]
    ),
    CONSTRAINT [FK_ProductVendor_Vendor_BusinessEntityID] FOREIGN KEY
    (
        [BusinessEntityID]
    ) REFERENCES [Purchasing].[Vendor](
        [BusinessEntityID]
    );
GO
"""


def test_every_constraint_of_a_multi_constraint_alter_is_parsed() -> None:
    [table] = parse(_DDL)
    refs = sorted((fk["columns"][0], fk["references_table"]) for fk in table.foreign_keys)
    assert refs == [
        ("BusinessEntityID", "Vendor"),
        ("ProductID", "Product"),
        ("UnitMeasureCode", "UnitMeasure"),
    ]
