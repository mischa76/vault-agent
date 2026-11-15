# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 229 requirement(s) and 29 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (16)

- **hub_product** — business key `ProductNumber`. A product, identified by its unique product number. _(requirements: REQ-001, REQ-002, REQ-004)_
- **hub_product_category** — business key `Name`. Top level of the merchandising hierarchy, identified by name. _(requirements: REQ-032, REQ-033)_
- **hub_product_subcategory** — business key `Name`. Second level of the merchandising hierarchy, identified by name. _(requirements: REQ-032, REQ-034)_
- **hub_product_model** — business key `Name`. Product model, identified by name; the level for design, catalogue and instructions. _(requirements: REQ-039, REQ-041)_
- **hub_culture** — business key `CultureID`. Language/locale designation identified by culture code. _(requirements: REQ-002-2)_
- **hub_product_description** — business key `ProductDescriptionID`. Free-text marketing description held in a library independent of products. _(requirements: REQ-001-2)_
- **hub_product_photo** — business key `ProductPhotoID`. Product photograph in the photo library. _(requirements: REQ-008-2)_
- **hub_illustration** — business key `IllustrationID`. Technical illustration used in manufacturing instructions. _(requirements: REQ-016-2, REQ-017-2)_
- **hub_document** — business key `DocumentNode`. Entry (document or folder) of the controlled document library, identified by its hierarchy node. _(requirements: REQ-020-2, REQ-021-2, REQ-023-2)_
- **hub_unit_measure** — business key `UnitMeasureCode`. Standard unit of measure identified by short code. _(requirements: REQ-056, REQ-057, REQ-058)_
- **hub_location** — business key `Name`. Manufacturing location / work centre, also an inventory-holding location, identified by name. _(requirements: REQ-001-3, REQ-002-3, REQ-007-3)_
- **hub_work_order** — business key `WorkOrderID`. Work order raised to manufacture a product. _(requirements: REQ-018-3, REQ-019-3)_
- **hub_work_order_operation** — business key `work_order_operation`. An operation of a work order, identified by work order and operation sequence. _(requirements: REQ-035-3, REQ-036-3)_
- **hub_scrap_reason** — business key `Name`. Standard scrap reason (failure description). _(requirements: REQ-025-3, REQ-026-3)_
- **hub_inventory_transaction** — business key `TransactionID`. Inventory transaction (stock movement), from live and archive stores as one continuous history. Integrated from 2 source(s): TransactionHistory.TransactionID, TransactionHistoryArchive.TransactionID; canonical staging key column `TRANSACTIONID`. _(requirements: REQ-001-4, REQ-002-4, REQ-018-4, REQ-019-4, REQ-020-4, REQ-023-4)_
- **hub_product_review** — business key `ProductReviewID`. Customer review of a product. _(requirements: REQ-024-4, REQ-025-4)_

### Links (17)

- **link_product_product_subcategory** — connects hub_product, hub_product_subcategory. Product placed in (at most one) subcategory. _(requirements: REQ-036, REQ-038)_
- **link_product_subcategory_product_category** — connects hub_product_subcategory, hub_product_category. Subcategory belongs to exactly one category. _(requirements: REQ-035, REQ-038)_
- **link_product_product_model** — connects hub_product, hub_product_model. Product belongs to at most one product model. _(requirements: REQ-040, REQ-041)_
- **link_product_size_unit_measure** — connects hub_product, hub_unit_measure (size). Unit of measure in which the product size is expressed. _(requirements: REQ-010, REQ-011, REQ-057)_
- **link_product_weight_unit_measure** — connects hub_product, hub_unit_measure (weight). Unit of measure in which the product weight is expressed. _(requirements: REQ-012, REQ-013, REQ-057)_
- **link_product_model_description_culture** — connects hub_product_model, hub_product_description, hub_culture. A product model's description in a specific culture. Unit of work: ProductModel + ProductDescription + Culture. _(requirements: REQ-003-2, REQ-004-2, REQ-005-2, REQ-006-2, REQ-007-2, REQ-047-3, REQ-048-3)_
- **link_product_product_photo** — connects hub_product, hub_product_photo. Many-to-many association of products and photographs. _(requirements: REQ-011-2, REQ-012-2, REQ-014-2, REQ-047-3)_
- **link_product_model_illustration** — connects hub_product_model, hub_illustration. Illustrations supporting product models. _(requirements: REQ-018-2, REQ-019-2, REQ-047-3)_
- **link_product_document** — connects hub_product, hub_document. Documents associated with products (many-to-many). _(requirements: REQ-039-2, REQ-040-2, REQ-047-3)_
- **link_document_business_entity** — connects hub_document, hub_business_entity. Document owner (an employee), joined to the HR area's business entity hub. _(requirements: REQ-025-2, REQ-026-2, REQ-027-2, REQ-049-3)_
- **link_product_assembly_component** — connects hub_product, hub_product (component), hub_unit_measure. Bill of materials: a component product used in an assembly product, quantity expressed in a unit of measure. Unit of work: ProductAssemblyID + ComponentID (+ UnitMeasureCode). Driving key: hub_product, hub_product (component). _(requirements: REQ-041-2, REQ-042-2, REQ-043-2, REQ-045-2, REQ-047, REQ-053)_
- **link_work_order_product** — connects hub_work_order, hub_product. Product being manufactured by a work order. _(requirements: REQ-020-3, REQ-034-3)_
- **link_work_order_scrap_reason** — connects hub_work_order, hub_scrap_reason. Scrap reason recorded on a work order (optional). _(requirements: REQ-025-3, REQ-027-3, REQ-028-3)_
- **link_work_order_operation_location** — connects hub_work_order_operation, hub_work_order, hub_product, hub_location. A work order operation, its work order, product manufactured and location where performed. Unit of work: WorkOrderRouting row: WorkOrderID, OperationSequence, ProductID, LocationID. _(requirements: REQ-035-3, REQ-037-3, REQ-038-3, REQ-051-2, REQ-052-2)_
- **link_product_location** — connects hub_product, hub_location. Inventory of a product held at a location. _(requirements: REQ-009-3, REQ-012-3, REQ-013-3, REQ-014-3)_
- **link_inventory_transaction_product** — connects hub_inventory_transaction, hub_product. Product moved by an inventory transaction. _(requirements: REQ-003-4, REQ-017-4)_
- **link_product_review_product** — connects hub_product_review, hub_product. Product a review relates to. _(requirements: REQ-026-4, REQ-032-4)_

### Satellites (30)

- **sat_product_details** — on hub_product; payload: Name, MakeFlag, FinishedGoodsFlag, Color, Size, Weight, DaysToManufacture, ProductLine, Class, Style, SafetyStockLevel, ReorderPoint, ModifiedDate. Descriptive product attributes. Split rationale: Slowly changing descriptive master data.. _(requirements: REQ-003, REQ-005, REQ-007, REQ-009, REQ-010, REQ-012, REQ-014, REQ-015, REQ-017, REQ-019, REQ-024, REQ-025, REQ-040-4)_
- **sat_product_pricing** — on hub_product; payload: StandardCost, ListPrice. Current standard cost and list price on the product record. Split rationale: Financial figures change more often than descriptive data.. _(requirements: REQ-021, REQ-022, REQ-023, REQ-058-2, REQ-066)_
- **sat_product_lifecycle** — on hub_product; payload: SellStartDate, SellEndDate, DiscontinuedDate. Sale availability and discontinuation dates. Split rationale: Lifecycle events change independently.. _(requirements: REQ-027, REQ-028, REQ-029, REQ-030, REQ-031)_
- **sat_product_cost_history** — on hub_product; payload: EndDate, StandardCost, ModifiedDate. Standard cost history periods. Multi-active satellite, child dependent key: StartDate. Source table: ProductCostHistory. _(requirements: REQ-053-2, REQ-054-2, REQ-055-2, REQ-056-2, REQ-057-2, REQ-060-2)_
- **sat_product_list_price_history** — on hub_product; payload: EndDate, ListPrice, ModifiedDate. List price history periods. Multi-active satellite, child dependent key: StartDate. Source table: ProductListPriceHistory. _(requirements: REQ-061-2, REQ-062, REQ-063, REQ-064, REQ-065, REQ-068, REQ-069)_
- **sat_product_category_details** — on hub_product_category; payload: ModifiedDate. Product category audit attributes. _(requirements: REQ-033, REQ-040-4)_
- **sat_product_subcategory_details** — on hub_product_subcategory; payload: ModifiedDate. Product subcategory audit attributes. _(requirements: REQ-034, REQ-040-4)_
- **sat_product_model_details** — on hub_product_model; payload: ModifiedDate. Product model audit attributes. _(requirements: REQ-039, REQ-040-4)_
- **sat_product_model_catalogue** — on hub_product_model; payload: CatalogDescription. Structured catalogue content of the model. Split rationale: Structured document content, separate data type.. _(requirements: REQ-042, REQ-043)_
- **sat_product_model_instructions** — on hub_product_model; payload: Instructions. Structured manufacturing instructions of the model. Split rationale: Structured document content, separate data type and audience.. _(requirements: REQ-044, REQ-045, REQ-046)_
- **sat_culture_details** — on hub_culture; payload: Name, ModifiedDate. Culture descriptive name. _(requirements: REQ-002-2)_
- **sat_product_description_details** — on hub_product_description; payload: Description, ModifiedDate. Free-text marketing description. _(requirements: REQ-001-2)_
- **sat_product_photo_details** — on hub_product_photo; payload: ThumbnailPhotoFileName, LargePhotoFileName, ModifiedDate. Photograph file names. _(requirements: REQ-009-2, REQ-010-2)_
- **sat_product_photo_images** — on hub_product_photo; payload: ThumbNailPhoto, LargePhoto. Binary photograph images. Split rationale: Binary content split from simple fields.. _(requirements: REQ-009-2, REQ-010-2, REQ-051-3)_
- **sat_illustration_details** — on hub_illustration; payload: Diagram, ModifiedDate. Illustration diagram. _(requirements: REQ-016-2, REQ-017-2)_
- **sat_document_details** — on hub_document; payload: DocumentLevel, Title, FolderFlag, FileName, FileExtension, Revision, ChangeNumber, Status, DocumentSummary, ModifiedDate. Document metadata, revision and approval control. _(requirements: REQ-021-2, REQ-022-2, REQ-024-2, REQ-028-2, REQ-029-2, REQ-030-2, REQ-031-2, REQ-032-2, REQ-033-2, REQ-035-2, REQ-036-2, REQ-037-2)_
- **sat_document_content** — on hub_document; payload: Document. Full binary document content. Split rationale: Binary content, inclusion to be confirmed.. _(requirements: REQ-038-2, REQ-051-3)_
- **sat_unit_measure_details** — on hub_unit_measure; payload: Name, ModifiedDate. Unit of measure name. _(requirements: REQ-056)_
- **sat_location_details** — on hub_location; payload: CostRate, Availability, ModifiedDate. Location hourly cost rate and capacity. _(requirements: REQ-003-3, REQ-004-3, REQ-005-3, REQ-006-3)_
- **sat_scrap_reason_details** — on hub_scrap_reason; payload: ModifiedDate. Scrap reason audit attributes. _(requirements: REQ-026-3)_
- **sat_work_order_details** — on hub_work_order; payload: OrderQty, StockedQty, ScrappedQty, StartDate, EndDate, DueDate, ModifiedDate. Work order quantities and dates. _(requirements: REQ-021-3, REQ-022-3, REQ-023-3, REQ-024-3, REQ-029-3, REQ-030-3, REQ-031-3, REQ-032-3, REQ-033-3)_
- **sat_work_order_operation_details** — on hub_work_order_operation; payload: ScheduledStartDate, ScheduledEndDate, ActualStartDate, ActualEndDate, ActualResourceHrs, PlannedCost, ActualCost, ModifiedDate. Operation schedule, actuals, hours and costs. _(requirements: REQ-039-3, REQ-040-3, REQ-041-3, REQ-042-3, REQ-043-3, REQ-045-3, REQ-046-3, REQ-047-2, REQ-048-2, REQ-049-2)_
- **sat_inventory_transaction_details** — on hub_inventory_transaction; payload: ReferenceOrderID, ReferenceOrderLineID, TransactionDate, TransactionType, Quantity, ActualCost, ModifiedDate. Live inventory transaction details. Source table: TransactionHistory. Split rationale: Split by source: live store.. _(requirements: REQ-004-4, REQ-005-4, REQ-006-4, REQ-008-4, REQ-009-4, REQ-011-4, REQ-050-3)_
- **sat_inventory_transaction_archive_details** — on hub_inventory_transaction; payload: ReferenceOrderID, ReferenceOrderLineID, TransactionDate, TransactionType, Quantity, ActualCost, ModifiedDate. Archived inventory transaction details. Source table: TransactionHistoryArchive. Split rationale: Split by source: archive store.. _(requirements: REQ-018-4, REQ-019-4, REQ-020-4)_
- **sat_product_review_details** — on hub_product_review; payload: ReviewDate, Rating, Comments, ModifiedDate. Review date, rating and comments. _(requirements: REQ-029-4, REQ-030-4, REQ-031-4, REQ-033-4)_
- **sat_product_review_reviewer_pii** — on hub_product_review; payload: ReviewerName, EmailAddress. Reviewer identity (personal data). Split rationale: PII classification split.. _(requirements: REQ-027-4, REQ-028-4, REQ-036-4, REQ-037-4, REQ-038-4)_
- **sat_product_location_inventory** — on link_product_location; payload: Shelf, Bin, Quantity, ModifiedDate. Current quantity at shelf and bin. _(requirements: REQ-009-3, REQ-010-3, REQ-011-3, REQ-016-3, REQ-017-3)_
- **sat_product_product_photo_details** — on link_product_product_photo; payload: Primary, ModifiedDate. Principal-image indicator. _(requirements: REQ-012-2, REQ-013-2, REQ-015-2)_
- **sat_product_assembly_component_effectivity** — on link_product_assembly_component; payload: StartDate, EndDate. Active period of a component in an assembly. Effectivity satellite. _(requirements: REQ-049, REQ-050, REQ-051, REQ-052)_
- **sat_product_assembly_component_details** — on link_product_assembly_component; payload: BOMLevel, PerAssemblyQty, ModifiedDate. Component quantity per assembly and BOM level. _(requirements: REQ-044-2, REQ-046-2, REQ-048, REQ-054, REQ-055)_

### Hub keys decided before modelling (9)

- **Culture** — key `CultureID`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `CultureID` (0.90); primary key `CultureID`.
- **Document** — key `DocumentNode`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `DocumentNode` (0.50); primary key `DocumentNode`.
- **Location** — key `Name`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `Name` (0.75); primary key `LocationID`.
- **Product** — key `ProductNumber`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `ProductNumber` (0.96); primary key `ProductID`.
- **ProductCategory** — key `Name`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `Name` (0.75); primary key `ProductCategoryID`.
- **ProductModel** — key `Name`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `Name` (0.72); primary key `ProductModelID`.
- **ProductSubcategory** — key `Name`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `Name` (0.72); primary key `ProductSubcategoryID`.
- **ScrapReason** — key `Name`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `Name` (0.50); primary key `ScrapReasonID`.
- **UnitMeasure** — key `UnitMeasureCode`: the primary key is itself a natural key; primary key `UnitMeasureCode`.

### Source mappings (105)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `ProductNumber` → `Product`.`ProductNumber` — exact_name, accepted
- `Name` → `ProductCategory`.`Name` — exact_name, accepted
- `Name` → `ProductSubcategory`.`Name` — exact_name, accepted
- `Name` → `ProductModel`.`Name` — exact_name, accepted
- `CultureID` → `Culture`.`CultureID` — exact_name, accepted
- `ProductDescriptionID` → `ProductDescription`.`ProductDescriptionID` — exact_name, accepted
- `ProductPhotoID` → `ProductPhoto`.`ProductPhotoID` — exact_name, accepted
- `IllustrationID` → `Illustration`.`IllustrationID` — exact_name, accepted
- `DocumentNode` → `Document`.`DocumentNode` — exact_name, accepted
- `UnitMeasureCode` → `UnitMeasure`.`UnitMeasureCode` — exact_name, accepted
- `Name` → `Location`.`Name` — exact_name, accepted
- `WorkOrderID` → `WorkOrder`.`WorkOrderID` — exact_name, accepted
- `Name` → `ScrapReason`.`Name` — exact_name, accepted
- `TransactionID` → `TransactionHistory`.`TransactionID` — exact_name, accepted
- `ProductReviewID` → `ProductReview`.`ProductReviewID` — exact_name, accepted
- `Name` → `Product`.`Name` — exact_name, accepted
- `MakeFlag` → `Product`.`MakeFlag` — exact_name, accepted
- `FinishedGoodsFlag` → `Product`.`FinishedGoodsFlag` — exact_name, accepted
- `Color` → `Product`.`Color` — exact_name, accepted
- `Size` → `Product`.`Size` — exact_name, accepted
- `Weight` → `Product`.`Weight` — exact_name, accepted
- `DaysToManufacture` → `Product`.`DaysToManufacture` — exact_name, accepted
- `ProductLine` → `Product`.`ProductLine` — exact_name, accepted
- `Class` → `Product`.`Class` — exact_name, accepted
- `Style` → `Product`.`Style` — exact_name, accepted
- `SafetyStockLevel` → `Product`.`SafetyStockLevel` — exact_name, accepted
- `ReorderPoint` → `Product`.`ReorderPoint` — exact_name, accepted
- `ModifiedDate` → `Product`.`ModifiedDate` — exact_name, accepted
- `StandardCost` → `Product`.`StandardCost` — exact_name, accepted
- `ListPrice` → `Product`.`ListPrice` — exact_name, accepted
- `SellStartDate` → `Product`.`SellStartDate` — exact_name, accepted
- `SellEndDate` → `Product`.`SellEndDate` — exact_name, accepted
- `DiscontinuedDate` → `Product`.`DiscontinuedDate` — exact_name, accepted
- `ModifiedDate` → `ProductCategory`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `ProductSubcategory`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `ProductModel`.`ModifiedDate` — exact_name, accepted
- `CatalogDescription` → `ProductModel`.`CatalogDescription` — exact_name, accepted
- `Instructions` → `ProductModel`.`Instructions` — exact_name, accepted
- `Name` → `Culture`.`Name` — exact_name, accepted
- `ModifiedDate` → `Culture`.`ModifiedDate` — exact_name, accepted
- `Description` → `ProductDescription`.`Description` — exact_name, accepted
- `ModifiedDate` → `ProductDescription`.`ModifiedDate` — exact_name, accepted
- `ThumbnailPhotoFileName` → `ProductPhoto`.`ThumbnailPhotoFileName` — exact_name, accepted
- `LargePhotoFileName` → `ProductPhoto`.`LargePhotoFileName` — exact_name, accepted
- `ModifiedDate` → `ProductPhoto`.`ModifiedDate` — exact_name, accepted
- `ThumbNailPhoto` → `ProductPhoto`.`ThumbNailPhoto` — exact_name, accepted
- `LargePhoto` → `ProductPhoto`.`LargePhoto` — exact_name, accepted
- `Diagram` → `Illustration`.`Diagram` — exact_name, accepted
- `ModifiedDate` → `Illustration`.`ModifiedDate` — exact_name, accepted
- `DocumentLevel` → `Document`.`DocumentLevel` — exact_name, accepted
- `Title` → `Document`.`Title` — exact_name, accepted
- `FolderFlag` → `Document`.`FolderFlag` — exact_name, accepted
- `FileName` → `Document`.`FileName` — exact_name, accepted
- `FileExtension` → `Document`.`FileExtension` — exact_name, accepted
- `Revision` → `Document`.`Revision` — exact_name, accepted
- `ChangeNumber` → `Document`.`ChangeNumber` — exact_name, accepted
- `Status` → `Document`.`Status` — exact_name, accepted
- `DocumentSummary` → `Document`.`DocumentSummary` — exact_name, accepted
- `ModifiedDate` → `Document`.`ModifiedDate` — exact_name, accepted
- `Document` → `Document`.`Document` — exact_name, accepted
- `Name` → `UnitMeasure`.`Name` — exact_name, accepted
- `ModifiedDate` → `UnitMeasure`.`ModifiedDate` — exact_name, accepted
- `CostRate` → `Location`.`CostRate` — exact_name, accepted
- `Availability` → `Location`.`Availability` — exact_name, accepted
- `ModifiedDate` → `Location`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `ScrapReason`.`ModifiedDate` — exact_name, accepted
- `OrderQty` → `WorkOrder`.`OrderQty` — exact_name, accepted
- `StockedQty` → `WorkOrder`.`StockedQty` — exact_name, accepted
- `ScrappedQty` → `WorkOrder`.`ScrappedQty` — exact_name, accepted
- `StartDate` → `WorkOrder`.`StartDate` — exact_name, accepted
- `EndDate` → `WorkOrder`.`EndDate` — exact_name, accepted
- `DueDate` → `WorkOrder`.`DueDate` — exact_name, accepted
- `ModifiedDate` → `WorkOrder`.`ModifiedDate` — exact_name, accepted
- `ScheduledStartDate` → `WorkOrderRouting`.`ScheduledStartDate` — exact_name, accepted
- `ScheduledEndDate` → `WorkOrderRouting`.`ScheduledEndDate` — exact_name, accepted
- `ActualStartDate` → `WorkOrderRouting`.`ActualStartDate` — exact_name, accepted
- `ActualEndDate` → `WorkOrderRouting`.`ActualEndDate` — exact_name, accepted
- `ActualResourceHrs` → `WorkOrderRouting`.`ActualResourceHrs` — exact_name, accepted
- `PlannedCost` → `WorkOrderRouting`.`PlannedCost` — exact_name, accepted
- `ActualCost` → `WorkOrderRouting`.`ActualCost` — exact_name, accepted
- `ModifiedDate` → `WorkOrderRouting`.`ModifiedDate` — exact_name, accepted
- `ReferenceOrderID` → `TransactionHistory`.`ReferenceOrderID` — exact_name, accepted
- `ReferenceOrderLineID` → `TransactionHistory`.`ReferenceOrderLineID` — exact_name, accepted
- `TransactionDate` → `TransactionHistory`.`TransactionDate` — exact_name, accepted
- `TransactionType` → `TransactionHistory`.`TransactionType` — exact_name, accepted
- `Quantity` → `TransactionHistory`.`Quantity` — exact_name, accepted
- `ActualCost` → `TransactionHistory`.`ActualCost` — exact_name, accepted
- `ModifiedDate` → `TransactionHistory`.`ModifiedDate` — exact_name, accepted
- `ReviewDate` → `ProductReview`.`ReviewDate` — exact_name, accepted
- `Rating` → `ProductReview`.`Rating` — exact_name, accepted
- `Comments` → `ProductReview`.`Comments` — exact_name, accepted
- `ModifiedDate` → `ProductReview`.`ModifiedDate` — exact_name, accepted
- `ReviewerName` → `ProductReview`.`ReviewerName` — exact_name, accepted
- `EmailAddress` → `ProductReview`.`EmailAddress` — exact_name, accepted
- `Shelf` → `ProductInventory`.`Shelf` — exact_name, accepted
- `Bin` → `ProductInventory`.`Bin` — exact_name, accepted
- `Quantity` → `ProductInventory`.`Quantity` — exact_name, accepted
- `ModifiedDate` → `ProductInventory`.`ModifiedDate` — exact_name, accepted
- `Primary` → `ProductProductPhoto`.`Primary` — exact_name, accepted
- `ModifiedDate` → `ProductProductPhoto`.`ModifiedDate` — exact_name, accepted
- `StartDate` → `BillOfMaterials`.`StartDate` — exact_name, accepted
- `EndDate` → `BillOfMaterials`.`EndDate` — exact_name, accepted
- `BOMLevel` → `BillOfMaterials`.`BOMLevel` — exact_name, accepted
- `PerAssemblyQty` → `BillOfMaterials`.`PerAssemblyQty` — exact_name, accepted
- `ModifiedDate` → `BillOfMaterials`.`ModifiedDate` — exact_name, accepted

No in-scope source — Business Vault / marts (1): hub_product::EndDate.

Unresolved — the mapper could not decide (1): WorkOrderRouting::work_order_operation.

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261115T082335567302Z`) carrying 10 hub(s), 6 link(s) and 26 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

42 construct(s) were left untouched and 0 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/production_requirements.md
- Generated dbt models: 105 raw-vault model(s) + 138 staging model(s) (see `state.artifacts`)
