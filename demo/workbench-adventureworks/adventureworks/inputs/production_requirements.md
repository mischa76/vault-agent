# Business Requirements: Production and Product Management Data Warehouse

## Document purpose

This document describes what the business needs to know and track in the production and product management area of our bicycle manufacturing and retail operation. It is written from the operational system that supports this area today, and it deliberately stops short of proposing any warehouse design. The intent is to state the business subject matter, the entities involved, what identifies them, what we need to know about them, and how they relate — so that a data modelling specialist can take it from here.

## Scope

The area covered is everything from the definition of a product, through how products are structured and manufactured, where they are stored, what they cost, what we sell them for, how they are described and illustrated for catalogue and marketing purposes, and how inventory moves. It excludes customers, sales orders as such, purchasing and supplier management, and human resources — those areas are owned by other parts of the business and are referenced here only where production data points at them.

This is the largest single area of our operational landscape. Roughly a quarter of the operational tables in the system belong to it.

---

## 1. Product — the central business entity

Everything in this area revolves around the product. A product in our business may be something we manufacture ourselves, something we buy in, a finished sellable item, or a component that never appears in a catalogue.

**REQ-001** The business must be able to identify every product uniquely and unambiguously. Products carry a product number that is stated to be unique — this is the identifier people use when talking about a product in day-to-day work, and it is the natural business key.

**REQ-002** Every product must carry a product name. The name is descriptive and is not guaranteed to be unique; it must not be relied on to identify a product.

**REQ-003** The business must know, for every product, whether it is manufactured in-house or purchased from outside. This is a fundamental distinction: it determines whether the product has a manufacturing route, a bill of materials, and work orders, or whether it arrives via purchasing.

**REQ-004** The business must know whether a product is a salable item or not. Many products in the catalogue are components and sub-assemblies that are never offered to a customer. Reporting on the product portfolio must be able to separate salable finished goods from internal-only items.

**REQ-005** The business must track product colour where it applies. Colour is a genuine merchandising attribute in our range and not all products have one.

**REQ-006** The business must track product size and the unit in which that size is expressed. Size is recorded as a short code or value, and separately the unit of measure that gives it meaning. The two must always be read together.

**REQ-007** The business must track product weight and, separately, the unit in which the weight is expressed. As with size, the weight figure is meaningless without its unit.

**REQ-008** The business must know how many days are required to manufacture a product. This figure supports lead-time planning and promise dates.

**REQ-009** Products are grouped into a product line. The lines recognised in the operational system are Road, Mountain, Touring and Standard. Reporting on the range, on sales performance and on manufacturing load is expected to be possible by product line.

**REQ-010** Products carry a class of High, Medium or Low. The business meaning of this classification is not stated in the source system. It is used in practice but its definition should be confirmed with the product management team before it is used as an analytical dimension.

**REQ-011** Products carry a style of Womens, Mens or Universal. This is a merchandising attribute and should be available for analysis of the range.

**REQ-012** The business must record the standard cost of a product — the cost figure used for costing and margin purposes.

**REQ-013** The business must record the list price of a product — the price at which it is offered for sale.

**REQ-014** The business must be able to compare list price against standard cost in order to understand the margin position of each product.

**REQ-015** The business must record two inventory control parameters for each product: the safety stock level (the minimum inventory quantity we intend to hold) and the reorder point (the inventory level at which a purchase order or a work order is triggered).

**REQ-016** The business must be able to compare actual inventory on hand against the safety stock level and the reorder point, in order to identify products at risk of stock-out and products where a replenishment action is overdue.

### Product lifecycle dates

**REQ-017** The business must know the date from which a product became available for sale.

**REQ-018** The business must know the date from which a product ceased to be available for sale, where that has happened. A product may be current, in which case no such date exists.

**REQ-019** The business must know the date on which a product was discontinued, where applicable. Discontinuation and the end of sale availability are recorded separately in the operational system and should be treated as two distinct business events; product management should confirm the difference in meaning between them.

**REQ-020** The business must be able to report on the active product range as at any point in time, using the sell start and sell end dates — for example, "which products were sellable in March of last year".

---

## 2. Product classification hierarchy

**REQ-021** Products are organised into a two-level classification: a product category, which is subdivided into product subcategories.

**REQ-022** A product category must be identifiable by its name (its description). Categories are the top level of the merchandising hierarchy — in our business these are the broad groupings such as bikes, components, clothing and accessories.

**REQ-023** A product subcategory must be identifiable by its name and must be known to belong to exactly one product category.

**REQ-024** A product belongs to at most one subcategory. Not every product is placed in a subcategory — components and internal items may sit outside the merchandising hierarchy entirely. Reporting must handle unclassified products gracefully rather than dropping them.

**REQ-025** The business must be able to roll up any product-level measure — inventory, cost, price, transaction volume, scrap — to subcategory and then to category level.

---

## 3. Product models

A product model is the design a product is built to. Several individual products — different sizes and colours of the same bicycle, for instance — can share one model.

**REQ-026** The business must be able to identify a product model by its name.

**REQ-027** A product belongs to at most one product model. As with subcategory, not every product has one.

**REQ-028** The business must be able to group and report products by product model, as this is the level at which design, catalogue content and manufacturing instructions are held.

**REQ-029** Detailed catalogue information is held at product model level, in a structured document format. The business needs this content available for catalogue and web publication purposes.

**REQ-030** Manufacturing instructions are held at product model level, also in a structured document format. Manufacturing and quality teams need access to the instructions that apply to a given model. Because these are structured documents rather than simple fields, the level of detail that can be extracted from them needs to be scoped separately with the manufacturing engineering team.

---

## 4. Product descriptions, cultures and multilingual catalogue content

**REQ-031** The business maintains a library of product descriptions — free-text marketing descriptions of products, held independently of any one product.

**REQ-032** The business maintains a list of cultures (language and locale designations), each identified by a short culture code and carrying a descriptive name.

**REQ-033** A product model is associated with a product description in a specific culture. This is how our catalogue supports multiple languages: the same model has different descriptions for different markets.

**REQ-034** The business must be able to report which models have catalogue descriptions in which cultures, and specifically which models are missing a description in a culture we sell into. This is a content-completeness question the marketing team needs answered.

**REQ-035** The combination of model, description and culture is the meaningful business fact. A description on its own tells us little; it becomes useful when we know which model it describes and in which language.

---

## 5. Product photography

**REQ-036** The business maintains a library of product photographs. Each photograph exists in a small (thumbnail) and a large version, and each version has its own image file and file name.

**REQ-037** A product may have several photographs, and a photograph may be used for more than one product.

**REQ-038** For each product, one photograph is designated the principal image. The business must be able to identify the principal image for a product, since this is the one used as the lead image in the catalogue and on the web.

**REQ-039** The business must be able to identify products that have no photograph at all, and products that have photographs but no designated principal image. Both are content gaps that marketing needs to close.

---

## 6. Illustrations

**REQ-040** The business maintains a set of illustrations used in manufacturing instructions. These are technical diagrams held in a structured format.

**REQ-041** An illustration is associated with one or more product models, and a product model may have several illustrations.

**REQ-042** The business must be able to determine which illustrations support which product models, so that manufacturing documentation can be assembled and kept complete.

---

## 7. Documents and engineering change control

The operational system holds a controlled document library. It is organised hierarchically — documents sit inside folders — and it carries approval and revision control.

**REQ-043** The business must be able to identify each document in the library and know its title.

**REQ-044** The business must know whether an entry in the library is a folder or an actual document, and must be able to reconstruct the folder structure, since documents are organised in a hierarchy and their depth in that hierarchy is recorded.

**REQ-045** Each document has an owner, who is an employee. The business must be able to report on documents by owner — for example, to find documents whose owner has left the company. Employee master data is owned outside this area and must be sourced from there.

**REQ-046** Each document carries a revision number. The business must be able to see which revision of a document is current.

**REQ-047** Each document is associated with an engineering change approval number. The business must be able to trace documents to the engineering change that authorised them.

**REQ-048** Each document has an approval status of Pending approval, Approved or Obsolete. The business must be able to report on documents by status — in particular, to find documents pending approval and documents still in circulation that are marked obsolete.

**REQ-049** Each document carries a file name and a file extension indicating its type (for example a word-processing document or a plain text file). The business needs to know the document type for archiving and access purposes.

**REQ-050** Each document has a short abstract or summary, distinct from the full document content. The summary is what most business reporting needs; the full binary document content is generally not required in analytical reporting and its inclusion should be confirmed rather than assumed.

**REQ-051** Documents are linked to products. A product may have several associated documents (assembly instructions, specifications, safety notices), and a document may apply to several products.

**REQ-052** The business must be able to identify manufactured products that have no associated document, as a documentation-completeness check.

---

## 8. Bill of materials — how products are assembled

This is one of the most important structures in the area: it describes how our products are put together from other products.

**REQ-053** A product may be assembled from other products. The business must be able to record, for a given assembly, which products are components of it.

**REQ-054** Both sides of an assembly relationship are products in their own right. A component in one assembly may itself be an assembly of further components, so the structure is recursive and can be several levels deep.

**REQ-055** The business must know, for each component in an assembly, the quantity of that component needed to make one of the assembly item.

**REQ-056** The business must know the unit of measure in which that component quantity is expressed. Quantity without unit is not actionable.

**REQ-057** The business must know how deep a component sits below its parent assembly — the level in the bill of materials. This supports both explosion of a bill of materials to raw components and summary reporting at a chosen level.

**REQ-058** Bill of materials relationships change over time. Each component-in-assembly relationship carries the date the component started being used in the assembly and the date it stopped being used. The business must therefore be able to answer "what was this product made of on a given date", not only "what is it made of now".

**REQ-059** The business must be able to identify currently active bill of materials relationships — those that have started and have not yet ended — as the default view for planning and costing.

**REQ-060** The business must be able to see component substitutions over time: where one component stopped being used in an assembly on a date and another started, this is a design change the engineering and cost teams need visibility of.

**REQ-061** The business must be able to determine, for any component, all the assemblies it is used in ("where used"), in order to assess the impact of a component shortage, price change or quality problem.

**REQ-062** The business must be able to cost an assembly from the costs of its components and the quantities required, and to compare that built-up cost with the assembly's recorded standard cost.

---

## 9. Units of measure

**REQ-063** The business maintains a standard list of units of measure, each identified by a short code and carrying a descriptive name.

**REQ-064** Units of measure are used in several places: the quantity of a component in an assembly, the unit for a product's size, and the unit for a product's weight. The same standard list serves all of them.

**REQ-065** All quantity and dimension reporting must present the unit alongside the figure, and must never aggregate figures expressed in different units without conversion. Whether conversion factors between units exist anywhere in the business needs clarification — they are not held in this system.

---

## 10. Manufacturing locations

**REQ-066** The business operates a number of manufacturing locations, each identified by a name. In practice these are the shop floors and work centres within our plant.

**REQ-067** Each location has a standard hourly cost rate. This is the rate used to cost the time products spend at that location.

**REQ-068** Each location has a stated work capacity expressed in hours. The business must be able to compare actual hours consumed at a location against its stated capacity, in order to identify bottlenecks and under-used capacity.

**REQ-069** Locations serve two distinct purposes in the business: they are where manufacturing operations are performed, and they are where inventory is held. Reporting must be able to address both uses of the same location.

---

## 11. Inventory

**REQ-070** The business must know the quantity of each product held at each location.

**REQ-071** Within a location, stock is stored in a specific shelf, and within a shelf, in a specific bin. The business must be able to report inventory down to shelf and bin level, since this is what stock-picking and stock-counting operations work with.

**REQ-072** The same product may be held at several locations, and a location holds many products. The meaningful business fact is the quantity of a given product at a given location in a given shelf and bin.

**REQ-073** The business must be able to total inventory for a product across all locations, and to total inventory at a location across all products.

**REQ-074** The business must be able to value inventory by combining quantities on hand with the applicable standard cost of the product.

**REQ-075** The operational system holds the current inventory position, not a history of it. If the business needs to report inventory levels as at past dates, that history has to be built by capturing the position over time — this is an explicit expectation on the warehouse and should be confirmed as a requirement with the supply chain team.

---

## 12. Work orders — manufacturing execution

**REQ-076** The business raises work orders to manufacture products. Each work order must be uniquely identifiable and must state which product is being made.

**REQ-077** Each work order states the quantity ordered.

**REQ-078** Each work order records the quantity actually stocked — that is, the good output that reached inventory.

**REQ-079** Each work order records the quantity scrapped.

**REQ-080** The business must be able to calculate and report a scrap rate: scrapped quantity against ordered quantity, by product, by product line, by category and over time. Scrap is a direct cost and a quality signal.

**REQ-081** Where a quantity was scrapped, the work order records a scrap reason. The business maintains a standard list of scrap reasons, each carrying a failure description.

**REQ-082** The business must be able to report scrap volumes and scrap costs by scrap reason, in order to prioritise quality improvement effort.

**REQ-083** Not every work order has a scrap reason — a work order completed without scrap will have none. Reporting must handle this.

**REQ-084** Each work order records a start date, an end date and a due date. The business must be able to report on manufacturing lead time (start to end) and on schedule adherence (end against due).

**REQ-085** The business must be able to identify work orders that are open — started but not ended — and work orders that are overdue against their due date.

**REQ-086** The business must be able to report work order volume and output over time, by product and by product grouping.

---

## 13. Work order routing — operations on the shop floor

A work order is executed as a sequence of operations, each performed at a location.

**REQ-087** Each work order is broken down into a sequence of operations. The business must know the sequence number of each operation, since the order in which they are performed is meaningful.

**REQ-088** Each operation is performed at a manufacturing location. The business must be able to report the manufacturing workload falling on each location.

**REQ-089** Each operation carries a scheduled start date and a scheduled end date.

**REQ-090** Each operation carries an actual start date and an actual end date. Both scheduled and actual must be retained: the comparison between them is the basis of schedule adherence reporting at the operation level.

**REQ-091** The business must be able to identify operations that are scheduled but not yet started, started but not yet finished, and completed, based on the presence of the actual dates.

**REQ-092** Each operation records the actual resource hours consumed. The business must be able to compare hours consumed at a location against that location's stated capacity.

**REQ-093** Each operation carries a planned cost and an actual cost. The business must be able to report cost variance at operation level, at work order level, at product level and at location level.

**REQ-094** The business must be able to combine actual resource hours with the location's standard hourly cost rate to understand how operation costs arise, and to reconcile that against the recorded actual cost.

**REQ-095** The business must be able to roll up all operations of a work order to give a total manufactured cost for that work order, and to compare it against the standard cost of the product manufactured.

**REQ-096** Each operation identifies the product being manufactured as well as the work order. The two are expected to agree; any disagreement is a data quality issue that should be flagged.

---

## 14. Cost history

**REQ-097** The standard cost of a product changes over time. The business maintains a history of standard cost for each product, with a start date and an end date defining the period during which each cost applied.

**REQ-098** The business must be able to determine the standard cost that applied to a product on any given date, not just the cost that applies now.

**REQ-099** The current standard cost period is the one with no end date. The business must be able to identify the currently applicable cost for every product.

**REQ-100** The business must be able to report cost movements over time — how the standard cost of a product, a product line or a category has changed, and by how much.

**REQ-101** The current product record also carries a standard cost figure. The business expects this to agree with the currently applicable entry in the cost history; a reconciliation between the two is required and any disagreement must be reported as a data quality issue.

**REQ-102** Historic transactions must be valued using the cost applicable at the time of the transaction, not today's cost, wherever the business is analysing margin or manufacturing cost over a period.

---

## 15. List price history

**REQ-103** The list price of a product changes over time. The business maintains a history of list price for each product, with a start date and an end date defining the period during which each price applied.

**REQ-104** The business must be able to determine the list price that applied to a product on any given date.

**REQ-105** The current list price period is the one with no end date. The business must be able to identify the currently applicable price for every product.

**REQ-106** The business must be able to report price movements over time — the frequency, size and direction of price changes by product, product line and category.

**REQ-107** As with cost, the current product record also carries a list price, and this is expected to agree with the currently applicable entry in the price history. A reconciliation is required.

**REQ-108** The business must be able to analyse margin over time by combining the list price applicable on a date with the standard cost applicable on the same date. Cost history and price history are maintained independently and their periods do not necessarily align, so margin analysis must handle overlapping but non-identical periods.

---

## 16. Inventory transactions

Every movement of stock is recorded as a transaction. This is the movement history behind the current inventory position.

**REQ-109** The business must be able to identify each inventory transaction uniquely.

**REQ-110** Each transaction states the product involved, the quantity moved, and the date and time it occurred.

**REQ-111** Each transaction states its type: work order, sales order or purchase order. The business must be able to separate manufacturing movements, outbound sales movements and inbound purchase movements.

**REQ-112** Each transaction refers to the originating order and to the specific line on that order. Depending on the transaction type, this refers to a work order, a sales order or a purchase order. The business must be able to trace a stock movement back to the document that caused it. Note that the order reference alone is ambiguous — it must always be read together with the transaction type to know which kind of order is meant.

**REQ-113** Each transaction carries an actual cost. The business must be able to value stock movements at the cost actually applied, and to report cost of goods manufactured, sold and purchased on that basis.

**REQ-114** The business must be able to reconcile the net effect of transactions for a product against the current inventory quantity held for that product, as a data quality and stock-accuracy control.

**REQ-115** Transactions do not record a location. Movement history is therefore available at product level but not at location level; if location-level movement analysis is required, this is a gap that needs raising with the operational system owners.

**REQ-116** The business must be able to report transaction volume and value over time, by product, product grouping, and transaction type.

### Archived transactions

**REQ-117** Older inventory transactions are moved out of the live operational store into an archive. The archive holds the same information as the live store: transaction identifier, product, order reference and line, date, type, quantity and actual cost.

**REQ-118** For long-run historical analysis, the business must be able to see live and archived transactions as one continuous history. Reporting that covers a multi-year period and looks only at the live store will silently under-report.

**REQ-119** The business needs clarity on the rule that governs when a transaction is archived, and confirmation that a transaction exists in exactly one of the two stores at any time and is never counted twice. This should be established with the operational system owners.

---

## 17. Product reviews

**REQ-120** Customers submit reviews of products. The business must be able to identify each review and know which product it relates to.

**REQ-121** Each review records the name of the reviewer, their e-mail address and the date the review was submitted.

**REQ-122** Each review carries a rating on a scale of one to five, with five the highest.

**REQ-123** Each review carries free-text comments from the reviewer.

**REQ-124** The business must be able to report average rating and review volume by product, by product model, by subcategory and by category, and to track how ratings move over time.

**REQ-125** The business must be able to identify products with consistently low ratings, so that quality and product management can act on them, and to relate poorly rated products to their scrap and manufacturing cost history.

**REQ-126** Reviewer e-mail addresses are personal data. Any use of review data in reporting must respect data protection obligations; how reviewer identity is handled in analytical reporting needs to be agreed with the data protection officer before this data is published in reports.

**REQ-127** Reviewers are identified only by name and e-mail address, with no link to our customer master. Whether a reviewer can or should be matched to a known customer is an open question for the customer data owners and is out of scope here.

---

## 18. Cross-cutting requirements

**REQ-128** Every record in the operational system carries the date and time it was last updated. The business needs this to understand the currency of the data it is looking at, and to detect records that have not been maintained.

**REQ-129** The business must be able to report the "as at" date of any figure presented, so that users know what point in time a report reflects.

**REQ-130** Historical accuracy matters in this area. Bills of materials, standard costs and list prices all change, and the operational system keeps history for each. Analysis of past periods must use the values that applied at the time, and must not be silently restated when a cost, price or assembly structure changes.

**REQ-131** Several relationships in this area are optional: a product may have no subcategory, no model, no photograph, no document, no review, and no bill of materials. Reporting must treat these absences as legitimate business situations, not as errors, while still being able to report on them as completeness gaps where that is the question being asked.

**REQ-132** Several relationships are many-to-many: products to documents, products to photographs, models to illustrations, and models to descriptions by culture. Each of these associations is a business fact in its own right and needs to be retained as such.

**REQ-133** Two references in this area point outside the production area entirely — the owner of a document is an employee, and inventory transactions refer to sales orders and purchase orders. The business needs these to join up with the human resources, sales and purchasing areas of the warehouse when those are built. Until then, they can only be reported as identifiers.

**REQ-134** Some content in this area is held as structured documents or as binary content rather than as simple fields: catalogue descriptions, manufacturing instructions, illustration diagrams, photograph images and full document content. What of this is genuinely needed for business reporting, and at what level of detail, needs to be agreed with marketing and manufacturing engineering rather than assumed.

**REQ-135** Where the operational system carries technical record identifiers that have no business meaning, these are of no interest to the business and should not surface in business reporting.

---

## Open questions requiring clarification

The following points could not be resolved from the operational system alone and need to be settled with the relevant business owners before the design work proceeds:

1. The business meaning of the product **Class** attribute (High / Medium / Low) — REQ-010.
2. The difference in meaning between a product's **sell end date** and its **discontinued date** — REQ-019.
3. Whether the business needs **historical inventory positions**, which the operational system does not keep — REQ-075.
4. Whether **conversion factors between units of measure** exist anywhere in the business — REQ-065.
5. The **archiving rule** for inventory transactions, and confirmation that a transaction is never in both stores — REQ-119.
6. The absence of a **location on inventory transactions**, and whether location-level movement analysis is needed — REQ-115.
7. Handling of **reviewer personal data** in analytical reporting — REQ-126, and whether reviewers should be matched to customers — REQ-127.
8. How much of the **structured and binary content** (catalogue XML, manufacturing instructions, illustrations, images, document bodies) is needed for reporting — REQ-134.
9. The level of detail that can usefully be extracted from **manufacturing instructions** held as structured documents — REQ-030.
