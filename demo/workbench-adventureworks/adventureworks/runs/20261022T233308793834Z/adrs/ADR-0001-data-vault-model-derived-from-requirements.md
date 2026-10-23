# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-10-23
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 210 requirement(s) and 30 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (16)

- **hub_product** — business key `ProductID`. Product (finished goods, components, sub-assemblies). Anchored on ProductID because every production relation (inventory, work orders, BOM, cost/price history, transactions, reviews) references products by ProductID; the day-to-day ProductNumber is carried in sat_product_details. _(requirements: REQ-001, REQ-002, REQ-052-3)_
- **hub_product_category** — business key `ProductCategoryID`. Top level of the merchandising hierarchy; name held in satellite. _(requirements: REQ-027, REQ-028)_
- **hub_product_subcategory** — business key `ProductSubcategoryID`. Second level of the product classification hierarchy. _(requirements: REQ-027, REQ-029)_
- **hub_product_model** — business key `ProductModelID`. Product model at which design, catalogue content and manufacturing instructions are held. _(requirements: REQ-034, REQ-036)_
- **hub_culture** — business key `CultureID`. Language/locale designation identified by a short culture code. _(requirements: REQ-041)_
- **hub_unit_measure** — business key `UnitMeasureCode`. Standard unit of measure used for size, weight and BOM quantities. _(requirements: REQ-084, REQ-085)_
- **hub_product_description** — business key `ProductDescriptionID`. Library entry of a free-text marketing description. _(requirements: REQ-040)_
- **hub_product_photo** — business key `ProductPhotoID`. Library entry of a product photograph. _(requirements: REQ-046)_
- **hub_illustration** — business key `IllustrationID`. Technical diagram used in manufacturing instructions. _(requirements: REQ-052)_
- **hub_document** — business key `DocumentNode`. Entry (folder or document) in the controlled document library, identified by its hierarchy node. _(requirements: REQ-055, REQ-057)_
- **hub_location** — business key `LocationID`. Manufacturing location / inventory holding location; referenced by LocationID in inventory and routing. _(requirements: REQ-001-2, REQ-005-2, REQ-006-2)_
- **hub_work_order** — business key `WorkOrderID`. Work order raised to manufacture a product. _(requirements: REQ-016-2, REQ-017-2)_
- **hub_work_order_operation** — business key `work_order_operation`. Operation within a work order, identified by work order plus operation sequence. _(requirements: REQ-034-2, REQ-035-2)_
- **hub_scrap_reason** — business key `ScrapReasonID`. Standard scrap reason. _(requirements: REQ-024-2)_
- **hub_inventory_transaction** — business key `TransactionID`. Inventory movement; live and archive stores feed the same hub so they form one continuous history. Integrated from 2 source(s): TransactionHistory.TransactionID, TransactionHistoryArchive.TransactionID; canonical staging key column `TRANSACTIONID`. _(requirements: REQ-001-3, REQ-002-3, REQ-018-3, REQ-019-3, REQ-020-3, REQ-023-3)_
- **hub_product_review** — business key `ProductReviewID`. Customer-submitted product review. _(requirements: REQ-024-3, REQ-025-3)_

### Links (16)

- **link_product_subcategory** — connects hub_product, hub_product_subcategory. Product placed in (at most one) subcategory. _(requirements: REQ-031, REQ-033)_
- **link_product_subcategory_category** — connects hub_product_subcategory, hub_product_category. Subcategory belongs to exactly one category. _(requirements: REQ-030, REQ-033)_
- **link_product_model** — connects hub_product, hub_product_model. Product belongs to at most one product model. _(requirements: REQ-035, REQ-036)_
- **link_product_unit_measure** — connects hub_product, hub_unit_measure (size), hub_unit_measure (weight). Units of measure in which a product's size and weight are expressed. _(requirements: REQ-009, REQ-010, REQ-085)_
- **link_product_model_description_culture** — connects hub_product_model, hub_product_description, hub_culture. Model described by a product description in a specific culture; the three-way combination is the business fact. Unit of work: ProductModelID + ProductDescriptionID + CultureID. _(requirements: REQ-042, REQ-043, REQ-044, REQ-045, REQ-047-3)_
- **link_product_model_illustration** — connects hub_product_model, hub_illustration. Illustrations supporting product models (many-to-many). _(requirements: REQ-053, REQ-054, REQ-047-3)_
- **link_product_product_photo** — connects hub_product, hub_product_photo. Photographs used for products (many-to-many). _(requirements: REQ-047, REQ-048, REQ-050, REQ-047-3)_
- **link_product_document** — connects hub_product, hub_document. Documents applying to products (many-to-many). _(requirements: REQ-069, REQ-070, REQ-047-3)_
- **link_document_business_entity** — connects hub_document, hub_business_entity. Document owner (employee, sourced from Document.Owner) joined to the existing HR business entity hub. _(requirements: REQ-058, REQ-059, REQ-060, REQ-048-3, REQ-049-3)_
- **link_bill_of_materials** — connects hub_product (assembly), hub_product (component), hub_unit_measure. Component-in-assembly relationship between two products, with the unit of the component quantity. Unit of work: ProductAssemblyID + ComponentID (+ UnitMeasureCode). Driving key: hub_product (assembly), hub_product (component). _(requirements: REQ-071, REQ-072, REQ-073, REQ-075, REQ-081, REQ-085)_
- **link_product_location** — connects hub_product, hub_location. Inventory holding of a product at a location. _(requirements: REQ-007-2, REQ-010-2, REQ-011-2, REQ-012-2)_
- **link_work_order_product** — connects hub_work_order, hub_product. Product being made by a work order. _(requirements: REQ-018-2, REQ-033-2)_
- **link_work_order_scrap_reason** — connects hub_work_order, hub_scrap_reason. Scrap reason recorded on a work order (optional). _(requirements: REQ-023-2, REQ-025-2, REQ-027-2)_
- **link_work_order_routing** — connects hub_work_order_operation, hub_work_order, hub_product, hub_location. Operation of a work order, the product manufactured and the location where it is performed. Unit of work: WorkOrderID + OperationSequence + ProductID + LocationID. _(requirements: REQ-034-2, REQ-036-2, REQ-037-2, REQ-050-2, REQ-051-2)_
- **link_inventory_transaction_product** — connects hub_inventory_transaction, hub_product. Product involved in an inventory transaction. _(requirements: REQ-003-3, REQ-014-3, REQ-017-3)_
- **link_product_review_product** — connects hub_product_review, hub_product. Product a review relates to. _(requirements: REQ-025-3, REQ-031-3)_

### Satellites (30)

- **sat_product_details** — on hub_product; payload: ProductNumber, Name, MakeFlag, FinishedGoodsFlag, Color, Size, Weight, DaysToManufacture, ProductLine, Class, Style, ModifiedDate. Descriptive product attributes including the natural product number. Source table: Product. Split rationale: Slowly changing descriptive attributes.. _(requirements: REQ-002, REQ-003, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-012, REQ-014, REQ-015, REQ-039-3)_
- **sat_product_pricing** — on hub_product; payload: StandardCost, ListPrice. Current standard cost and list price on the product record. Source table: Product. Split rationale: Changes more frequently than descriptive attributes.. _(requirements: REQ-016, REQ-017, REQ-018, REQ-058-2, REQ-067-2)_
- **sat_product_inventory_policy** — on hub_product; payload: SafetyStockLevel, ReorderPoint. Inventory planning parameters. Source table: Product. Split rationale: Planning parameters change independently.. _(requirements: REQ-019, REQ-020, REQ-021)_
- **sat_product_lifecycle** — on hub_product; payload: SellStartDate, SellEndDate, DiscontinuedDate. Sale availability and discontinuation dates. Source table: Product. Split rationale: Lifecycle events change on their own cadence.. _(requirements: REQ-022, REQ-023, REQ-024, REQ-025, REQ-026)_
- **sat_product_cost_history** — on hub_product; payload: EndDate, StandardCost, ModifiedDate. Standard cost periods per product. Multi-active satellite, child dependent key: StartDate. Source table: ProductCostHistory. Split rationale: Separate source at finer grain (product + start date).. _(requirements: REQ-052-2, REQ-053-2, REQ-054-2, REQ-055-2, REQ-056-2, REQ-057-2, REQ-059-2, REQ-060-2)_
- **sat_product_list_price_history** — on hub_product; payload: EndDate, ListPrice, ModifiedDate. List price periods per product. Multi-active satellite, child dependent key: StartDate. Source table: ProductListPriceHistory. Split rationale: Separate source at finer grain (product + start date).. _(requirements: REQ-061-2, REQ-062-2, REQ-063-2, REQ-064-2, REQ-065-2, REQ-066-2, REQ-068-2, REQ-069-2, REQ-070-2)_
- **sat_product_category_details** — on hub_product_category; payload: Name, ModifiedDate. Category name. Source table: ProductCategory. _(requirements: REQ-028)_
- **sat_product_subcategory_details** — on hub_product_subcategory; payload: Name, ModifiedDate. Subcategory name. Source table: ProductSubcategory. _(requirements: REQ-029)_
- **sat_product_model_details** — on hub_product_model; payload: Name, ModifiedDate. Product model name. Source table: ProductModel. _(requirements: REQ-034)_
- **sat_product_model_content** — on hub_product_model; payload: CatalogDescription, Instructions. Structured catalogue description and manufacturing instructions. Source table: ProductModel. Split rationale: Large structured-document data type, inclusion to be confirmed.. _(requirements: REQ-037, REQ-038, REQ-039, REQ-051-3)_
- **sat_culture_details** — on hub_culture; payload: Name, ModifiedDate. Culture name. Source table: Culture. _(requirements: REQ-041)_
- **sat_unit_measure_details** — on hub_unit_measure; payload: Name, ModifiedDate. Unit of measure name. Source table: UnitMeasure. _(requirements: REQ-084, REQ-086)_
- **sat_product_description_details** — on hub_product_description; payload: Description, ModifiedDate. Marketing description text. Source table: ProductDescription. _(requirements: REQ-040)_
- **sat_product_photo_details** — on hub_product_photo; payload: ThumbnailPhotoFileName, LargePhotoFileName, ModifiedDate. Photo file names. Source table: ProductPhoto. _(requirements: REQ-046)_
- **sat_product_photo_image** — on hub_product_photo; payload: ThumbNailPhoto, LargePhoto. Binary photo images. Source table: ProductPhoto. Split rationale: Binary data type, inclusion to be confirmed.. _(requirements: REQ-046, REQ-051-3)_
- **sat_illustration_details** — on hub_illustration; payload: Diagram, ModifiedDate. Structured technical diagram. Source table: Illustration. _(requirements: REQ-052, REQ-051-3)_
- **sat_document_details** — on hub_document; payload: Title, FolderFlag, DocumentLevel, FileName, FileExtension, Revision, ChangeNumber, Status, DocumentSummary, ModifiedDate. Document metadata: title, folder flag, hierarchy depth, file, revision, engineering change, status, summary. Source table: Document. _(requirements: REQ-055, REQ-056, REQ-057, REQ-061, REQ-062, REQ-063, REQ-064, REQ-065, REQ-066, REQ-067)_
- **sat_document_content** — on hub_document; payload: Document. Full binary document content. Source table: Document. Split rationale: Binary data type, inclusion to be confirmed.. _(requirements: REQ-068, REQ-051-3)_
- **sat_location_details** — on hub_location; payload: Name, CostRate, Availability, ModifiedDate. Location name, hourly cost rate and capacity hours. Source table: Location. _(requirements: REQ-001-2, REQ-002-2, REQ-003-2, REQ-004-2, REQ-046-2)_
- **sat_work_order_details** — on hub_work_order; payload: OrderQty, StockedQty, ScrappedQty, StartDate, EndDate, DueDate, ModifiedDate. Work order quantities and dates. Source table: WorkOrder. _(requirements: REQ-019-2, REQ-020-2, REQ-021-2, REQ-022-2, REQ-028-2, REQ-029-2, REQ-030-2, REQ-031-2, REQ-032-2)_
- **sat_scrap_reason_details** — on hub_scrap_reason; payload: Name, ModifiedDate. Scrap reason failure description. Source table: ScrapReason. _(requirements: REQ-024-2)_
- **sat_work_order_operation_details** — on hub_work_order_operation; payload: ScheduledStartDate, ScheduledEndDate, ActualStartDate, ActualEndDate, ActualResourceHrs, PlannedCost, ActualCost, ModifiedDate. Scheduled/actual dates, resource hours and costs of an operation. Multi-active satellite, child dependent key: ProductID. Source table: WorkOrderRouting. Split rationale: WorkOrderRouting is unique on WorkOrderID + ProductID + OperationSequence; ProductID distinguishes concurrent rows per operation key.. _(requirements: REQ-038-2, REQ-039-2, REQ-040-2, REQ-041-2, REQ-042-2, REQ-043-2, REQ-044-2, REQ-045-2, REQ-047-2, REQ-048-2)_
- **sat_inventory_transaction_details** — on hub_inventory_transaction; payload: TransactionDate, TransactionType, Quantity, ActualCost, ReferenceOrderID, ReferenceOrderLineID, ModifiedDate. Live-store transaction details; order reference kept as identifiers read with transaction type until sales/purchasing areas exist. Source table: TransactionHistory. Split rationale: Split by source system: live store.. _(requirements: REQ-004-3, REQ-005-3, REQ-006-3, REQ-007-3, REQ-008-3, REQ-009-3, REQ-010-3, REQ-011-3, REQ-012-3, REQ-013-3, REQ-050-3)_
- **sat_inventory_transaction_archive** — on hub_inventory_transaction; payload: TransactionDate, TransactionType, Quantity, ActualCost, ReferenceOrderID, ReferenceOrderLineID, ModifiedDate. Archived transaction details, same information as the live store. Source table: TransactionHistoryArchive. Split rationale: Split by source system: archive store.. _(requirements: REQ-018-3, REQ-019-3, REQ-020-3, REQ-021-3)_
- **sat_product_review_details** — on hub_product_review; payload: ReviewDate, Rating, Comments, ModifiedDate. Review date, rating and comments. Source table: ProductReview. _(requirements: REQ-028-3, REQ-029-3, REQ-030-3, REQ-031-3, REQ-032-3, REQ-033-3)_
- **sat_product_review_reviewer_pii** — on hub_product_review; payload: ReviewerName, EmailAddress. Reviewer identity (personal data). Source table: ProductReview. Split rationale: PII classification split.. _(requirements: REQ-026-3, REQ-027-3, REQ-035-3, REQ-036-3, REQ-037-3)_
- **sat_product_location_inventory** — on link_product_location; payload: Quantity, ModifiedDate. Quantity on hand per shelf and bin; history built by capture over time. Multi-active satellite, child dependent key: Shelf, Bin. Source table: ProductInventory. _(requirements: REQ-008-2, REQ-009-2, REQ-010-2, REQ-013-2, REQ-014-2, REQ-015-2, REQ-021)_
- **sat_bill_of_materials_effectivity** — on link_bill_of_materials; payload: StartDate, EndDate. Active period of a component in an assembly. Effectivity satellite. Source table: BillOfMaterials. _(requirements: REQ-077, REQ-078, REQ-079, REQ-080, REQ-042-3, REQ-043-3)_
- **sat_bill_of_materials_details** — on link_bill_of_materials; payload: PerAssemblyQty, BOMLevel, ModifiedDate. Component quantity per assembly and BOM level. Multi-active satellite, child dependent key: StartDate. Source table: BillOfMaterials. Split rationale: BillOfMaterials is unique on ProductAssemblyID + ComponentID + StartDate; StartDate distinguishes concurrent rows per link key.. _(requirements: REQ-074, REQ-076, REQ-082, REQ-083)_
- **sat_product_product_photo_details** — on link_product_product_photo; payload: Primary, ModifiedDate. Principal-image flag for a product photograph. Source table: ProductProductPhoto. _(requirements: REQ-048, REQ-049, REQ-051)_

### Source mappings (109)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `ProductID` → `Product`.`ProductID` — exact_name, accepted
- `ProductCategoryID` → `ProductCategory`.`ProductCategoryID` — exact_name, accepted
- `ProductSubcategoryID` → `ProductSubcategory`.`ProductSubcategoryID` — exact_name, accepted
- `ProductModelID` → `ProductModel`.`ProductModelID` — exact_name, accepted
- `CultureID` → `Culture`.`CultureID` — exact_name, accepted
- `UnitMeasureCode` → `UnitMeasure`.`UnitMeasureCode` — exact_name, accepted
- `ProductDescriptionID` → `ProductDescription`.`ProductDescriptionID` — exact_name, accepted
- `ProductPhotoID` → `ProductPhoto`.`ProductPhotoID` — exact_name, accepted
- `IllustrationID` → `Illustration`.`IllustrationID` — exact_name, accepted
- `DocumentNode` → `Document`.`DocumentNode` — exact_name, accepted
- `LocationID` → `Location`.`LocationID` — exact_name, accepted
- `WorkOrderID` → `WorkOrder`.`WorkOrderID` — exact_name, accepted
- `ScrapReasonID` → `ScrapReason`.`ScrapReasonID` — exact_name, accepted
- `TransactionID` → `TransactionHistory`.`TransactionID` — exact_name, accepted
- `ProductReviewID` → `ProductReview`.`ProductReviewID` — exact_name, accepted
- `ProductNumber` → `Product`.`ProductNumber` — exact_name, accepted
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
- `ModifiedDate` → `Product`.`ModifiedDate` — exact_name, accepted
- `StandardCost` → `Product`.`StandardCost` — exact_name, accepted
- `ListPrice` → `Product`.`ListPrice` — exact_name, accepted
- `SafetyStockLevel` → `Product`.`SafetyStockLevel` — exact_name, accepted
- `ReorderPoint` → `Product`.`ReorderPoint` — exact_name, accepted
- `SellStartDate` → `Product`.`SellStartDate` — exact_name, accepted
- `SellEndDate` → `Product`.`SellEndDate` — exact_name, accepted
- `DiscontinuedDate` → `Product`.`DiscontinuedDate` — exact_name, accepted
- `Name` → `ProductCategory`.`Name` — exact_name, accepted
- `ModifiedDate` → `ProductCategory`.`ModifiedDate` — exact_name, accepted
- `Name` → `ProductSubcategory`.`Name` — exact_name, accepted
- `ModifiedDate` → `ProductSubcategory`.`ModifiedDate` — exact_name, accepted
- `Name` → `ProductModel`.`Name` — exact_name, accepted
- `ModifiedDate` → `ProductModel`.`ModifiedDate` — exact_name, accepted
- `CatalogDescription` → `ProductModel`.`CatalogDescription` — exact_name, accepted
- `Instructions` → `ProductModel`.`Instructions` — exact_name, accepted
- `Name` → `Culture`.`Name` — exact_name, accepted
- `ModifiedDate` → `Culture`.`ModifiedDate` — exact_name, accepted
- `Name` → `UnitMeasure`.`Name` — exact_name, accepted
- `ModifiedDate` → `UnitMeasure`.`ModifiedDate` — exact_name, accepted
- `Description` → `ProductDescription`.`Description` — exact_name, accepted
- `ModifiedDate` → `ProductDescription`.`ModifiedDate` — exact_name, accepted
- `ThumbnailPhotoFileName` → `ProductPhoto`.`ThumbnailPhotoFileName` — exact_name, accepted
- `LargePhotoFileName` → `ProductPhoto`.`LargePhotoFileName` — exact_name, accepted
- `ModifiedDate` → `ProductPhoto`.`ModifiedDate` — exact_name, accepted
- `ThumbNailPhoto` → `ProductPhoto`.`ThumbNailPhoto` — exact_name, accepted
- `LargePhoto` → `ProductPhoto`.`LargePhoto` — exact_name, accepted
- `Diagram` → `Illustration`.`Diagram` — exact_name, accepted
- `ModifiedDate` → `Illustration`.`ModifiedDate` — exact_name, accepted
- `Title` → `Document`.`Title` — exact_name, accepted
- `FolderFlag` → `Document`.`FolderFlag` — exact_name, accepted
- `DocumentLevel` → `Document`.`DocumentLevel` — exact_name, accepted
- `FileName` → `Document`.`FileName` — exact_name, accepted
- `FileExtension` → `Document`.`FileExtension` — exact_name, accepted
- `Revision` → `Document`.`Revision` — exact_name, accepted
- `ChangeNumber` → `Document`.`ChangeNumber` — exact_name, accepted
- `Status` → `Document`.`Status` — exact_name, accepted
- `DocumentSummary` → `Document`.`DocumentSummary` — exact_name, accepted
- `ModifiedDate` → `Document`.`ModifiedDate` — exact_name, accepted
- `Document` → `Document`.`Document` — exact_name, accepted
- `Name` → `Location`.`Name` — exact_name, accepted
- `CostRate` → `Location`.`CostRate` — exact_name, accepted
- `Availability` → `Location`.`Availability` — exact_name, accepted
- `ModifiedDate` → `Location`.`ModifiedDate` — exact_name, accepted
- `OrderQty` → `WorkOrder`.`OrderQty` — exact_name, accepted
- `StockedQty` → `WorkOrder`.`StockedQty` — exact_name, accepted
- `ScrappedQty` → `WorkOrder`.`ScrappedQty` — exact_name, accepted
- `StartDate` → `WorkOrder`.`StartDate` — exact_name, accepted
- `EndDate` → `WorkOrder`.`EndDate` — exact_name, accepted
- `DueDate` → `WorkOrder`.`DueDate` — exact_name, accepted
- `ModifiedDate` → `WorkOrder`.`ModifiedDate` — exact_name, accepted
- `Name` → `ScrapReason`.`Name` — exact_name, accepted
- `ModifiedDate` → `ScrapReason`.`ModifiedDate` — exact_name, accepted
- `ScheduledStartDate` → `WorkOrderRouting`.`ScheduledStartDate` — exact_name, accepted
- `ScheduledEndDate` → `WorkOrderRouting`.`ScheduledEndDate` — exact_name, accepted
- `ActualStartDate` → `WorkOrderRouting`.`ActualStartDate` — exact_name, accepted
- `ActualEndDate` → `WorkOrderRouting`.`ActualEndDate` — exact_name, accepted
- `ActualResourceHrs` → `WorkOrderRouting`.`ActualResourceHrs` — exact_name, accepted
- `PlannedCost` → `WorkOrderRouting`.`PlannedCost` — exact_name, accepted
- `ActualCost` → `WorkOrderRouting`.`ActualCost` — exact_name, accepted
- `ModifiedDate` → `WorkOrderRouting`.`ModifiedDate` — exact_name, accepted
- `TransactionDate` → `TransactionHistory`.`TransactionDate` — exact_name, accepted
- `TransactionType` → `TransactionHistory`.`TransactionType` — exact_name, accepted
- `Quantity` → `TransactionHistory`.`Quantity` — exact_name, accepted
- `ActualCost` → `TransactionHistory`.`ActualCost` — exact_name, accepted
- `ReferenceOrderID` → `TransactionHistory`.`ReferenceOrderID` — exact_name, accepted
- `ReferenceOrderLineID` → `TransactionHistory`.`ReferenceOrderLineID` — exact_name, accepted
- `ModifiedDate` → `TransactionHistory`.`ModifiedDate` — exact_name, accepted
- `ReviewDate` → `ProductReview`.`ReviewDate` — exact_name, accepted
- `Rating` → `ProductReview`.`Rating` — exact_name, accepted
- `Comments` → `ProductReview`.`Comments` — exact_name, accepted
- `ModifiedDate` → `ProductReview`.`ModifiedDate` — exact_name, accepted
- `ReviewerName` → `ProductReview`.`ReviewerName` — exact_name, accepted
- `EmailAddress` → `ProductReview`.`EmailAddress` — exact_name, accepted
- `Quantity` → `ProductInventory`.`Quantity` — exact_name, accepted
- `ModifiedDate` → `ProductInventory`.`ModifiedDate` — exact_name, accepted
- `StartDate` → `BillOfMaterials`.`StartDate` — exact_name, accepted
- `EndDate` → `BillOfMaterials`.`EndDate` — exact_name, accepted
- `PerAssemblyQty` → `BillOfMaterials`.`PerAssemblyQty` — exact_name, accepted
- `BOMLevel` → `BillOfMaterials`.`BOMLevel` — exact_name, accepted
- `ModifiedDate` → `BillOfMaterials`.`ModifiedDate` — exact_name, accepted
- `Primary` → `ProductProductPhoto`.`Primary` — exact_name, accepted
- `ModifiedDate` → `ProductProductPhoto`.`ModifiedDate` — exact_name, accepted

No in-scope source — Business Vault / marts (1): hub_product::EndDate.

Unresolved — the mapper could not decide (1): WorkOrderRouting::work_order_operation.

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261022T233041709632Z`) carrying 10 hub(s), 6 link(s) and 27 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

43 construct(s) were left untouched and 0 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/production_requirements.md
- Generated dbt models: 105 raw-vault model(s) + 93 staging model(s) (see `state.artifacts`)
