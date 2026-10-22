# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-10-22
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 218 requirement(s) and 29 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (15)

- **hub_product** — business key `ProductID`. Product master. ProductNumber is the business-recognised natural key (REQ-002), but every dependent relation (inventory, work orders, BOM, cost/price history, transactions, reviews, photos, documents) carries only ProductID. The hub is therefore anchored on ProductID so those relations can attach, and ProductNumber is kept as a descriptive attribute. _(requirements: REQ-001, REQ-002, REQ-048-3)_
- **hub_product_category** — business key `ProductCategoryID`. Top level of the merchandising hierarchy. Anchored on the ID because ProductSubcategory references categories by ID; Name is kept in a satellite. _(requirements: REQ-032, REQ-033)_
- **hub_product_subcategory** — business key `ProductSubcategoryID`. Second level of the merchandising hierarchy. Anchored on the ID because Product references subcategories by ID; Name is kept in a satellite. _(requirements: REQ-032, REQ-034)_
- **hub_product_model** — business key `ProductModelID`. Product model shared by several products. Anchored on the ID because Product and the association tables reference models by ID; Name is kept in a satellite. _(requirements: REQ-040, REQ-041, REQ-044)_
- **hub_culture** — business key `CultureID`. Language/locale designation, identified by a short culture code. _(requirements: REQ-049)_
- **hub_unit_measure** — business key `UnitMeasureCode`. Standard unit of measure, identified by a short code. _(requirements: REQ-095, REQ-096)_
- **hub_product_description** — business key `ProductDescriptionID`. Free-text marketing description held in a library, independent of any one product. _(requirements: REQ-048)_
- **hub_product_photo** — business key `ProductPhotoID`. Photograph in the product photo library. _(requirements: REQ-054, REQ-055)_
- **hub_illustration** — business key `IllustrationID`. Technical diagram used in manufacturing instructions. _(requirements: REQ-061)_
- **hub_document** — business key `DocumentNode`. Entry (document or folder) in the hierarchical controlled document library. _(requirements: REQ-064, REQ-065)_
- **hub_location** — business key `LocationID`. Manufacturing location / inventory location. Anchored on the ID because inventory and routing reference locations by ID; Name is kept in a satellite. _(requirements: REQ-001-2, REQ-006-2)_
- **hub_scrap_reason** — business key `ScrapReasonID`. Standard scrap reason. Anchored on the ID because WorkOrder references scrap reasons by ID. _(requirements: REQ-026-2)_
- **hub_work_order** — business key `WorkOrderID`. Work order raised to manufacture a product. _(requirements: REQ-018-2, REQ-019-2)_
- **hub_inventory_transaction** — business key `TransactionID`. Inventory transaction (stock movement), fed by both the live and the archive store so they form one continuous history. Integrated from 2 source(s): TransactionHistory.TransactionID, TransactionHistoryArchive.TransactionID; canonical staging key column `TRANSACTIONID`. _(requirements: REQ-001-3, REQ-002-3, REQ-016-3, REQ-017-3, REQ-018-3)_
- **hub_product_review** — business key `ProductReviewID`. Customer review of a product. _(requirements: REQ-022-3, REQ-023-3)_

### Links (16)

- **link_product_product_subcategory** — connects hub_product, hub_product_subcategory. A product belongs to at most one subcategory. The link is optional. _(requirements: REQ-036, REQ-037, REQ-039)_
- **link_product_subcategory_product_category** — connects hub_product_subcategory, hub_product_category. A subcategory belongs to exactly one category. _(requirements: REQ-035, REQ-039)_
- **link_product_product_model** — connects hub_product, hub_product_model. A product belongs to at most one product model. _(requirements: REQ-041, REQ-042, REQ-043, REQ-044)_
- **link_product_unit_measure** — connects hub_product, hub_unit_measure (size), hub_unit_measure (weight). Units of measure in which a product's size and weight are expressed. _(requirements: REQ-010, REQ-011, REQ-012, REQ-013, REQ-096)_
- **link_product_assembly_component** — connects hub_product (assembly), hub_product (component), hub_unit_measure. Bill of materials. An assembly product is made of a component product, with the component quantity expressed in a unit of measure. The structure is recursive. Unit of work: ProductAssemblyID + ComponentID (+ UnitMeasureCode). Driving key: hub_product (assembly), hub_product (component). _(requirements: REQ-082, REQ-083, REQ-085, REQ-088, REQ-092)_
- **link_product_model_description_culture** — connects hub_product_model, hub_product_description, hub_culture. A product model described by a product description in a specific culture. Unit of work: ProductModelID + ProductDescriptionID + CultureID. _(requirements: REQ-050, REQ-051, REQ-052, REQ-053, REQ-043-3, REQ-044-3)_
- **link_product_model_illustration** — connects hub_product_model, hub_illustration. Many-to-many association of illustrations with product models. _(requirements: REQ-062, REQ-063, REQ-043-3)_
- **link_product_product_photo** — connects hub_product, hub_product_photo. Many-to-many association of products with photographs. _(requirements: REQ-056, REQ-059, REQ-043-3)_
- **link_product_document** — connects hub_product, hub_document. Many-to-many association of products with documents. _(requirements: REQ-080, REQ-081, REQ-043-3)_
- **link_document_business_entity** — connects hub_document, hub_business_entity. Document owner. The owner is an employee held in the existing HR hub (Document.Owner maps to BusinessEntityID). _(requirements: REQ-068, REQ-069, REQ-070, REQ-045-3, REQ-046-3)_
- **link_product_location** — connects hub_product, hub_location. Inventory: a product held at a location (many-to-many). _(requirements: REQ-008-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2)_
- **link_work_order_product** — connects hub_work_order, hub_product. The product a work order manufactures. _(requirements: REQ-020-2, REQ-035-2)_
- **link_work_order_scrap_reason** — connects hub_work_order, hub_scrap_reason. Scrap reason recorded on a work order. The link is optional. _(requirements: REQ-025-2, REQ-027-2, REQ-028-2)_
- **link_work_order_product_location** — connects hub_work_order, hub_product, hub_location. Work order routing: operations of a work order for a product, performed at a manufacturing location. Unit of work: WorkOrderID + ProductID + LocationID (operation sequence as dependent key). _(requirements: REQ-036-2, REQ-038-2, REQ-039-2, REQ-053-2)_
- **link_inventory_transaction_product** — connects hub_inventory_transaction, hub_product. The product moved by an inventory transaction. _(requirements: REQ-003-3, REQ-012-3, REQ-015-3)_
- **link_product_review_product** — connects hub_product_review, hub_product. The product a review relates to. _(requirements: REQ-023-3, REQ-027-3)_

### Satellites (29)

- **sat_product_details** — on hub_product; payload: ProductNumber, Name, MakeFlag, FinishedGoodsFlag, Color, Size, Weight, DaysToManufacture, ProductLine, Class, Style, ModifiedDate. Descriptive product attributes, including the natural product number. Split rationale: Slowly changing descriptive classification of the product.. _(requirements: REQ-002, REQ-003, REQ-005, REQ-007, REQ-009, REQ-010, REQ-012, REQ-014, REQ-015, REQ-017, REQ-019, REQ-020)_
- **sat_product_pricing** — on hub_product; payload: StandardCost, ListPrice. Current standard cost and list price. Split rationale: Financial figures that change at a different rate from descriptive attributes.. _(requirements: REQ-021, REQ-022, REQ-023, REQ-060-2, REQ-068-2)_
- **sat_product_inventory_policy** — on hub_product; payload: SafetyStockLevel, ReorderPoint. Inventory planning parameters. Split rationale: Supply-chain planning parameters, maintained separately.. _(requirements: REQ-024, REQ-025, REQ-026)_
- **sat_product_lifecycle** — on hub_product; payload: SellStartDate, SellEndDate, DiscontinuedDate. Sale availability and discontinuation dates. Split rationale: Lifecycle events with their own rate of change.. _(requirements: REQ-027, REQ-028, REQ-029, REQ-030, REQ-031)_
- **sat_product_cost_history** — on hub_product; payload: EndDate, StandardCost, ModifiedDate. Standard cost history periods per product. Multi-active satellite, child dependent key: StartDate. Source table: ProductCostHistory. Split rationale: Separate source relation at finer grain (one row per cost period).. _(requirements: REQ-055-2, REQ-056-2, REQ-057-2, REQ-058-2, REQ-059-2, REQ-061-2, REQ-062-2)_
- **sat_product_list_price_history** — on hub_product; payload: EndDate, ListPrice, ModifiedDate. List price history periods per product. Multi-active satellite, child dependent key: StartDate. Source table: ProductListPriceHistory. Split rationale: Separate source relation at finer grain (one row per price period).. _(requirements: REQ-063-2, REQ-064-2, REQ-065-2, REQ-066-2, REQ-067-2, REQ-069-2, REQ-070-2, REQ-071-2)_
- **sat_product_category_details** — on hub_product_category; payload: Name, ModifiedDate. Category name. _(requirements: REQ-033)_
- **sat_product_subcategory_details** — on hub_product_subcategory; payload: Name, ModifiedDate. Subcategory name. _(requirements: REQ-034)_
- **sat_product_model_details** — on hub_product_model; payload: Name, ModifiedDate. Product model name. _(requirements: REQ-040)_
- **sat_product_model_content** — on hub_product_model; payload: CatalogDescription, Instructions. Structured catalogue description and manufacturing instructions. Split rationale: Large structured-document content, split from the lightweight descriptive data by data type.. _(requirements: REQ-045, REQ-046, REQ-047, REQ-047-3)_
- **sat_culture_details** — on hub_culture; payload: Name, ModifiedDate. Culture name. _(requirements: REQ-049)_
- **sat_unit_measure_details** — on hub_unit_measure; payload: Name, ModifiedDate. Unit of measure name. _(requirements: REQ-095, REQ-097)_
- **sat_product_description_details** — on hub_product_description; payload: Description, ModifiedDate. Free-text marketing description. _(requirements: REQ-048)_
- **sat_product_photo_details** — on hub_product_photo; payload: ThumbnailPhotoFileName, LargePhotoFileName, ModifiedDate. Photo file names for the thumbnail and large versions. _(requirements: REQ-055)_
- **sat_product_photo_images** — on hub_product_photo; payload: ThumbNailPhoto, LargePhoto. Binary images for the thumbnail and large versions. Split rationale: Binary content split out by data type; whether it is needed is still to be agreed.. _(requirements: REQ-055, REQ-047-3)_
- **sat_illustration_diagram** — on hub_illustration; payload: Diagram, ModifiedDate. Structured technical diagram. _(requirements: REQ-061, REQ-047-3)_
- **sat_document_details** — on hub_document; payload: DocumentLevel, Title, FolderFlag, FileName, FileExtension, Revision, ChangeNumber, Status, DocumentSummary, ModifiedDate. Document metadata: title, folder flag, hierarchy level, revision, engineering change number, approval status, file name and type, and summary. Full binary content is excluded until confirmed. _(requirements: REQ-065, REQ-066, REQ-067, REQ-071, REQ-072, REQ-073, REQ-074, REQ-075, REQ-076, REQ-077, REQ-078, REQ-079)_
- **sat_location_details** — on hub_location; payload: Name, CostRate, Availability, ModifiedDate. Location name, standard hourly cost rate and capacity in hours. _(requirements: REQ-001-2, REQ-002-2, REQ-003-2, REQ-004-2, REQ-005-2)_
- **sat_scrap_reason_details** — on hub_scrap_reason; payload: Name, ModifiedDate. Scrap reason failure description. _(requirements: REQ-026-2)_
- **sat_work_order_details** — on hub_work_order; payload: OrderQty, StockedQty, ScrappedQty, StartDate, EndDate, DueDate, ModifiedDate. Work order quantities and dates. _(requirements: REQ-021-2, REQ-022-2, REQ-023-2, REQ-024-2, REQ-030-2, REQ-031-2, REQ-032-2, REQ-033-2, REQ-034-2)_
- **sat_work_order_product_location_operation** — on link_work_order_product_location; payload: ScheduledStartDate, ScheduledEndDate, ActualStartDate, ActualEndDate, ActualResourceHrs, PlannedCost, ActualCost, ModifiedDate. Operation details for each operation sequence: scheduled and actual dates, resource hours and costs. Multi-active satellite, child dependent key: OperationSequence. Source table: WorkOrderRouting. _(requirements: REQ-037-2, REQ-040-2, REQ-041-2, REQ-042-2, REQ-043-2, REQ-044-2, REQ-045-2, REQ-047-2, REQ-048-2, REQ-049-2, REQ-050-2, REQ-051-2)_
- **sat_product_location_inventory** — on link_product_location; payload: Quantity, ModifiedDate. Quantity on hand per shelf and bin. Captured over time to build inventory history. Multi-active satellite, child dependent key: Shelf, Bin. Source table: ProductInventory. _(requirements: REQ-009-2, REQ-010-2, REQ-012-2, REQ-015-2, REQ-016-2, REQ-017-2)_
- **sat_product_product_photo_details** — on link_product_product_photo; payload: Primary, ModifiedDate. Flag marking the principal image of the product. _(requirements: REQ-057, REQ-058, REQ-060)_
- **sat_product_assembly_component_effectivity** — on link_product_assembly_component; payload: StartDate, EndDate. Period during which a component is used in an assembly. Effectivity satellite. _(requirements: REQ-088, REQ-089, REQ-090, REQ-091, REQ-038-3, REQ-039-3)_
- **sat_product_assembly_component_details** — on link_product_assembly_component; payload: BOMLevel, PerAssemblyQty, ModifiedDate. Bill of materials level and component quantity per assembly. _(requirements: REQ-084, REQ-086, REQ-087, REQ-093, REQ-094)_
- **sat_inventory_transaction_details** — on hub_inventory_transaction; payload: TransactionDate, TransactionType, ReferenceOrderID, ReferenceOrderLineID, Quantity, ActualCost, ModifiedDate. Live-store transaction details. The order reference is kept as an identifier and is read together with the transaction type. Source table: TransactionHistory. Split rationale: Split by source: live store.. _(requirements: REQ-003-3, REQ-004-3, REQ-005-3, REQ-006-3, REQ-007-3, REQ-008-3, REQ-009-3, REQ-010-3, REQ-011-3, REQ-046-3)_
- **sat_inventory_transaction_archive** — on hub_inventory_transaction; payload: TransactionDate, TransactionType, ReferenceOrderID, ReferenceOrderLineID, Quantity, ActualCost, ModifiedDate. Archived transaction details, which together with the live store form one continuous history. Source table: TransactionHistoryArchive. Split rationale: Split by source: archive store.. _(requirements: REQ-016-3, REQ-017-3, REQ-018-3, REQ-019-3, REQ-021-3)_
- **sat_product_review_details** — on hub_product_review; payload: ReviewDate, Rating, Comments, ModifiedDate. Review date, rating and comments. _(requirements: REQ-024-3, REQ-025-3, REQ-026-3, REQ-027-3, REQ-028-3, REQ-029-3)_
- **sat_product_review_reviewer_pii** — on hub_product_review; payload: ReviewerName, EmailAddress. Reviewer identity (personal data). Split rationale: Split out as personal data under data protection classification.. _(requirements: REQ-024-3, REQ-031-3, REQ-032-3, REQ-033-3)_

### Source mappings (108)

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
- `ScrapReasonID` → `ScrapReason`.`ScrapReasonID` — exact_name, accepted
- `WorkOrderID` → `WorkOrder`.`WorkOrderID` — exact_name, accepted
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
- `Name` → `Location`.`Name` — exact_name, accepted
- `CostRate` → `Location`.`CostRate` — exact_name, accepted
- `Availability` → `Location`.`Availability` — exact_name, accepted
- `ModifiedDate` → `Location`.`ModifiedDate` — exact_name, accepted
- `Name` → `ScrapReason`.`Name` — exact_name, accepted
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
- `Quantity` → `ProductInventory`.`Quantity` — exact_name, accepted
- `ModifiedDate` → `ProductInventory`.`ModifiedDate` — exact_name, accepted
- `Primary` → `ProductProductPhoto`.`Primary` — exact_name, accepted
- `ModifiedDate` → `ProductProductPhoto`.`ModifiedDate` — exact_name, accepted
- `StartDate` → `BillOfMaterials`.`StartDate` — exact_name, accepted
- `EndDate` → `BillOfMaterials`.`EndDate` — exact_name, accepted
- `BOMLevel` → `BillOfMaterials`.`BOMLevel` — exact_name, accepted
- `PerAssemblyQty` → `BillOfMaterials`.`PerAssemblyQty` — exact_name, accepted
- `ModifiedDate` → `BillOfMaterials`.`ModifiedDate` — exact_name, accepted
- `TransactionDate` → `TransactionHistory`.`TransactionDate` — exact_name, accepted
- `TransactionType` → `TransactionHistory`.`TransactionType` — exact_name, accepted
- `ReferenceOrderID` → `TransactionHistory`.`ReferenceOrderID` — exact_name, accepted
- `ReferenceOrderLineID` → `TransactionHistory`.`ReferenceOrderLineID` — exact_name, accepted
- `Quantity` → `TransactionHistory`.`Quantity` — exact_name, accepted
- `ActualCost` → `TransactionHistory`.`ActualCost` — exact_name, accepted
- `ModifiedDate` → `TransactionHistory`.`ModifiedDate` — exact_name, accepted
- `ReviewDate` → `ProductReview`.`ReviewDate` — exact_name, accepted
- `Rating` → `ProductReview`.`Rating` — exact_name, accepted
- `Comments` → `ProductReview`.`Comments` — exact_name, accepted
- `ModifiedDate` → `ProductReview`.`ModifiedDate` — exact_name, accepted
- `ReviewerName` → `ProductReview`.`ReviewerName` — exact_name, accepted
- `EmailAddress` → `ProductReview`.`EmailAddress` — exact_name, accepted

No in-scope source — Business Vault / marts (1): hub_product::EndDate.

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261021T232716713739Z`) carrying 10 hub(s), 7 link(s) and 27 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

44 construct(s) were left untouched and 0 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/production_requirements.md
- Generated dbt models: 104 raw-vault model(s) + 73 staging model(s) (see `state.artifacts`)
