<!-- Drafted deterministically from the AdventureWorks catalogue (Microsoft, MIT — see
NOTICE) by eval.adventureworks.draft_requirements: tables, descriptions, keys and foreign
keys as the catalogue states them. No analyst has read or written this. The C1 experiment,
2026-10-30. -->

# Requirements drafted from the source catalogue: production

**Area:** Production  
**Prepared by:** nobody — drafted from the catalogue  
**Status:** Draft, unreviewed

## 1. Purpose

The business needs to analyse what the production area of the operational system records. This document lists what that area records, as the system's own catalogue describes it: its tables, what identifies each, what each records, and how they refer to one another. It states nothing the catalogue does not.

## 2. Business entities in scope

| Concept | What the catalogue says it is |
|---|---|
| Bill of materials | Items required to make bicycles and bicycle subassemblies. It identifies the heirarchical relationship between a parent product and its components. |
| Culture | Lookup table containing the languages in which some AdventureWorks data is stored. |
| Document | Product maintenance documents. |
| Illustration | Bicycle assembly diagrams. |
| Location | Product inventory and manufacturing locations. |
| Product | Products sold or used in the manfacturing of sold products. |
| Product category | High-level product categorization. |
| Product cost history | Changes in the cost of a product over time. |
| Product description | Product descriptions in several languages. |
| Product document (a relationship) | Cross-reference table mapping products to related product documents. |
| Product inventory (a relationship) | Product inventory information. |
| Product list price history | Changes in the list price of a product over time. |
| Product model | Product model classification. |
| Product model illustration (a relationship) | Cross-reference table mapping product models and illustrations. |
| Product model product description culture (a relationship) | Cross-reference table mapping product descriptions and the language the description is written in. |
| Product photo | Product images. |
| Product product photo (a relationship) | Cross-reference table mapping products and product photos. |
| Product review | Customer reviews of products they have purchased. |
| Product subcategory | Product subcategories. See ProductCategory table. |
| Scrap reason | Manufacturing failure reasons lookup table. |
| Transaction history | Record of each purchase order, sales order, or work order transaction year to date. |
| Transaction history archive | Transactions for previous years. |
| Unit measure | Unit of measure lookup table. |
| Work order | (no description in the catalogue) |
| Work order routing | (no description in the catalogue) |

## 3. Bill of materials

Items required to make bicycles and bicycle subassemblies. It identifies the heirarchical relationship between a parent product and its components.

- **REQ-001** The business must record every **bill of materials**.
- **REQ-002** Each bill of materials is identified by the combination of **product assembly id**, **component id**, **start date**.
- **REQ-003** The business must record the **end date** of each bill of materials: Date the component stopped being used in the assembly item.
- **REQ-004** The business must record the **bom level** of each bill of materials: Indicates the depth the component is from its parent (AssemblyID).
- **REQ-005** The business must record the **per assembly qty** of each bill of materials: Quantity of the component needed to create the assembly.
- **REQ-006** Each bill of materials refers to one **product** (by its product assembly id).
- **REQ-007** Each bill of materials refers to one **product** (by its component id).
- **REQ-008** Each bill of materials refers to one **unit measure** (by its unit measure code).
- **REQ-009** Each bill of materials carries a last-changed timestamp.

## 4. Culture

Lookup table containing the languages in which some AdventureWorks data is stored.

- **REQ-010** The business must record every **culture**.
- **REQ-011** Each culture is identified by its **name**.
- **REQ-012** Each culture carries a last-changed timestamp.

## 5. Document

Product maintenance documents.

- **REQ-013** The business must record every **document**.
- **REQ-014** Each document is identified by its **document node**.
- **REQ-015** The business must record the **document level** of each document: Depth in the document hierarchy.
- **REQ-016** The business must record the **title** of each document: Title of the document.
- **REQ-017** The business must record the **folder flag** of each document: 0 = This is a folder, 1 = This is a document.
- **REQ-018** The business must record the **file name** of each document: File name of the document
- **REQ-019** The business must record the **file extension** of each document: File extension indicating the document type. For example, .doc or .txt.
- **REQ-020** The business must record the **revision** of each document: Revision number of the document.
- **REQ-021** The business must record the **change number** of each document: Engineering change approval number.
- **REQ-022** The business must record the **status** of each document: 1 = Pending approval, 2 = Approved, 3 = Obsolete
- **REQ-023** The business must record the **document summary** of each document: Document abstract.
- **REQ-024** The business must record the **document** of each document: Complete document.
- **REQ-025** Each document refers to one **employee** (by its owner).
- **REQ-026** Each document carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 6. Illustration

Bicycle assembly diagrams.

- **REQ-027** The business must record every **illustration**.
- **REQ-028** Each illustration is identified by its **illustration id**.
- **REQ-029** The business must record the **diagram** of each illustration: Illustrations used in manufacturing instructions. Stored as XML.
- **REQ-030** Each illustration carries a last-changed timestamp.

## 7. Location

Product inventory and manufacturing locations.

- **REQ-031** The business must record every **location**.
- **REQ-032** Each location is identified by its **name**.
- **REQ-033** The business must record the **cost rate** of each location: Standard hourly cost of the manufacturing location.
- **REQ-034** The business must record the **availability** of each location: Work capacity (in hours) of the manufacturing location.
- **REQ-035** Each location carries a last-changed timestamp.

## 8. Product

Products sold or used in the manfacturing of sold products.

- **REQ-036** The business must record every **product**.
- **REQ-037** Each product is identified by its **product number**.
- **REQ-038** The business must record the **name** of each product: Name of the product.
- **REQ-039** The business must record the **make flag** of each product: 0 = Product is purchased, 1 = Product is manufactured in-house.
- **REQ-040** The business must record the **finished goods flag** of each product: 0 = Product is not a salable item. 1 = Product is salable.
- **REQ-041** The business must record the **color** of each product: Product color.
- **REQ-042** The business must record the **safety stock level** of each product: Minimum inventory quantity.
- **REQ-043** The business must record the **reorder point** of each product: Inventory level that triggers a purchase order or work order.
- **REQ-044** The business must record the **standard cost** of each product: Standard cost of the product.
- **REQ-045** The business must record the **list price** of each product: Selling price.
- **REQ-046** The business must record the **size** of each product: Product size.
- **REQ-047** The business must record the **weight** of each product: Product weight.
- **REQ-048** The business must record the **days to manufacture** of each product: Number of days required to manufacture the product.
- **REQ-049** The business must record the **product line** of each product: R = Road, M = Mountain, T = Touring, S = Standard
- **REQ-050** The business must record the **class** of each product: H = High, M = Medium, L = Low
- **REQ-051** The business must record the **style** of each product: W = Womens, M = Mens, U = Universal
- **REQ-052** The business must record the **sell start date** of each product: Date the product was available for sale.
- **REQ-053** The business must record the **sell end date** of each product: Date the product was no longer available for sale.
- **REQ-054** The business must record the **discontinued date** of each product: Date the product was discontinued.
- **REQ-055** Each product refers to one **unit measure** (by its size unit measure code).
- **REQ-056** Each product refers to one **unit measure** (by its weight unit measure code).
- **REQ-057** Each product refers to one **product model** (by its product model id).
- **REQ-058** Each product refers to one **product subcategory** (by its product subcategory id).
- **REQ-059** Each product carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 9. Product category

High-level product categorization.

- **REQ-060** The business must record every **product category**.
- **REQ-061** Each product category is identified by its **name**.
- **REQ-062** Each product category carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 10. Product cost history

Changes in the cost of a product over time.

- **REQ-063** The business must record every **product cost history**.
- **REQ-064** Each product cost history is identified by the combination of **product id**, **start date**.
- **REQ-065** The business must record the **end date** of each product cost history: Product cost end date.
- **REQ-066** The business must record the **standard cost** of each product cost history: Standard cost of the product.
- **REQ-067** Each product cost history refers to one **product** (by its product id).
- **REQ-068** Each product cost history carries a last-changed timestamp.

## 11. Product description

Product descriptions in several languages.

- **REQ-069** The business must record every **product description**.
- **REQ-070** Each product description is identified by its **product description id**.
- **REQ-071** The business must record the **description** of each product description: Description of the product.
- **REQ-072** Each product description carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 12. Product document

Cross-reference table mapping products to related product documents.

- **REQ-073** The business must record which **product**, **document** are related, as a **product document**.
- **REQ-074** Each product document is identified by the combination of **product id**, **document node**.
- **REQ-075** Each product document carries a last-changed timestamp.

## 13. Product inventory

Product inventory information.

- **REQ-076** The business must record which **location**, **product** are related, as a **product inventory**.
- **REQ-077** Each product inventory is identified by the combination of **product id**, **location id**.
- **REQ-078** The business must record the **shelf** of each product inventory: Storage compartment within an inventory location.
- **REQ-079** The business must record the **bin** of each product inventory: Storage container on a shelf in an inventory location.
- **REQ-080** The business must record the **quantity** of each product inventory: Quantity of products in the inventory location.
- **REQ-081** Each product inventory carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 14. Product list price history

Changes in the list price of a product over time.

- **REQ-082** The business must record every **product list price history**.
- **REQ-083** Each product list price history is identified by the combination of **product id**, **start date**.
- **REQ-084** The business must record the **end date** of each product list price history: List price end date
- **REQ-085** The business must record the **list price** of each product list price history: Product list price.
- **REQ-086** Each product list price history refers to one **product** (by its product id).
- **REQ-087** Each product list price history carries a last-changed timestamp.

## 15. Product model

Product model classification.

- **REQ-088** The business must record every **product model**.
- **REQ-089** Each product model is identified by its **name**.
- **REQ-090** The business must record the **catalog description** of each product model: Detailed product catalog information in xml format.
- **REQ-091** The business must record the **instructions** of each product model: Manufacturing instructions in xml format.
- **REQ-092** Each product model carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 16. Product model illustration

Cross-reference table mapping product models and illustrations.

- **REQ-093** The business must record which **product model**, **illustration** are related, as a **product model illustration**.
- **REQ-094** Each product model illustration is identified by the combination of **product model id**, **illustration id**.
- **REQ-095** Each product model illustration carries a last-changed timestamp.

## 17. Product model product description culture

Cross-reference table mapping product descriptions and the language the description is written in.

- **REQ-096** The business must record which **product description**, **culture**, **product model** are related, as a **product model product description culture**.
- **REQ-097** Each product model product description culture is identified by the combination of **product model id**, **product description id**, **culture id**.
- **REQ-098** Each product model product description culture carries a last-changed timestamp.

## 18. Product photo

Product images.

- **REQ-099** The business must record every **product photo**.
- **REQ-100** Each product photo is identified by its **product photo id**.
- **REQ-101** The business must record the **thumb nail photo** of each product photo: Small image of the product.
- **REQ-102** The business must record the **thumbnail photo file name** of each product photo: Small image file name.
- **REQ-103** The business must record the **large photo** of each product photo: Large image of the product.
- **REQ-104** The business must record the **large photo file name** of each product photo: Large image file name.
- **REQ-105** Each product photo carries a last-changed timestamp.

## 19. Product product photo

Cross-reference table mapping products and product photos.

- **REQ-106** The business must record which **product**, **product photo** are related, as a **product product photo**.
- **REQ-107** Each product product photo is identified by the combination of **product id**, **product photo id**.
- **REQ-108** The business must record the **primary** of each product product photo: 0 = Photo is not the principal image. 1 = Photo is the principal image.
- **REQ-109** Each product product photo carries a last-changed timestamp.

## 20. Product review

Customer reviews of products they have purchased.

- **REQ-110** The business must record every **product review**.
- **REQ-111** Each product review is identified by its **product review id**.
- **REQ-112** The business must record the **reviewer name** of each product review: Name of the reviewer.
- **REQ-113** The business must record the **review date** of each product review: Date review was submitted.
- **REQ-114** The business must record the **email address** of each product review: Reviewer's e-mail address.
- **REQ-115** The business must record the **rating** of each product review: Product rating given by the reviewer. Scale is 1 to 5 with 5 as the highest rating.
- **REQ-116** The business must record the **comments** of each product review: Reviewer's comments
- **REQ-117** Each product review refers to one **product** (by its product id).
- **REQ-118** Each product review carries a last-changed timestamp.

## 21. Product subcategory

Product subcategories. See ProductCategory table.

- **REQ-119** The business must record every **product subcategory**.
- **REQ-120** Each product subcategory is identified by its **name**.
- **REQ-121** Each product subcategory refers to one **product category** (by its product category id).
- **REQ-122** Each product subcategory carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 22. Scrap reason

Manufacturing failure reasons lookup table.

- **REQ-123** The business must record every **scrap reason**.
- **REQ-124** Each scrap reason is identified by its **name**.
- **REQ-125** Each scrap reason carries a last-changed timestamp.

## 23. Transaction history

Record of each purchase order, sales order, or work order transaction year to date.

- **REQ-126** The business must record every **transaction history**.
- **REQ-127** Each transaction history is identified by its **transaction id**.
- **REQ-128** The business must record the **reference order id** of each transaction history: Purchase order, sales order, or work order identification number.
- **REQ-129** The business must record the **reference order line id** of each transaction history: Line number associated with the purchase order, sales order, or work order.
- **REQ-130** The business must record the **transaction date** of each transaction history: Date and time of the transaction.
- **REQ-131** The business must record the **transaction type** of each transaction history: W = WorkOrder, S = SalesOrder, P = PurchaseOrder
- **REQ-132** The business must record the **quantity** of each transaction history: Product quantity.
- **REQ-133** The business must record the **actual cost** of each transaction history: Product cost.
- **REQ-134** Each transaction history refers to one **product** (by its product id).
- **REQ-135** Each transaction history carries a last-changed timestamp.

## 24. Transaction history archive

Transactions for previous years.

- **REQ-136** The business must record every **transaction history archive**.
- **REQ-137** Each transaction history archive is identified by its **transaction id**.
- **REQ-138** The business must record the **product id** of each transaction history archive: Product identification number. Foreign key to Product.ProductID.
- **REQ-139** The business must record the **reference order id** of each transaction history archive: Purchase order, sales order, or work order identification number.
- **REQ-140** The business must record the **reference order line id** of each transaction history archive: Line number associated with the purchase order, sales order, or work order.
- **REQ-141** The business must record the **transaction date** of each transaction history archive: Date and time of the transaction.
- **REQ-142** The business must record the **transaction type** of each transaction history archive: W = Work Order, S = Sales Order, P = Purchase Order
- **REQ-143** The business must record the **quantity** of each transaction history archive: Product quantity.
- **REQ-144** The business must record the **actual cost** of each transaction history archive: Product cost.
- **REQ-145** Each transaction history archive carries a last-changed timestamp.

## 25. Unit measure

Unit of measure lookup table.

- **REQ-146** The business must record every **unit measure**.
- **REQ-147** Each unit measure is identified by its **name**.
- **REQ-148** Each unit measure carries a last-changed timestamp.

## 26. Work order

- **REQ-149** The business must record every **work order**.
- **REQ-150** Each work order is identified by its **work order id**.
- **REQ-151** The business must also record, for each work order: **order qty**, **stocked qty**, **scrapped qty**, **start date**, **end date**, **due date**.
- **REQ-152** Each work order refers to one **product** (by its product id).
- **REQ-153** Each work order refers to one **scrap reason** (by its scrap reason id).
- **REQ-154** Each work order carries a last-changed timestamp.

## 27. Work order routing

- **REQ-155** The business must record every **work order routing**.
- **REQ-156** Each work order routing is identified by the combination of **work order id**, **product id**, **operation sequence**.
- **REQ-157** The business must also record, for each work order routing: **scheduled start date**, **scheduled end date**, **actual start date**, **actual end date**, **actual resource hrs**, **planned cost**, **actual cost**.
- **REQ-158** Each work order routing refers to one **location** (by its location id).
- **REQ-159** Each work order routing refers to one **work order** (by its work order id).
- **REQ-160** Each work order routing carries a last-changed timestamp.
