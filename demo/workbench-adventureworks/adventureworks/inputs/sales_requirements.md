# Business Requirements: Sales Data Warehouse

**Area:** Sales operations — customers, sales orders, sales force, territories, pricing/promotions, currency and tax
**Author:** Business Analysis
**Status:** Draft for review
**Basis:** Technical schema of the `Sales` area of the operational system (19 tables), including the column descriptions maintained in that system.

---

## 1. Purpose and scope

The company sells bicycles and related products through two distinct channels: directly to individual consumers who order online, and through reseller stores served by our own sales representatives. Today, the operational sales system holds the record of what was sold, to whom, by whom, at what price, in which territory and in which currency — but that record is only usable transaction by transaction. The business needs a consolidated, historical view of sales activity for reporting, performance management and planning.

This document describes **what the business needs to know and track** in the sales area. It does not propose how that information should be stored or modelled.

### 1.1 In scope

- Customers (both individual consumers and reseller stores) and their commercial identity
- Sales orders and their individual order lines
- The reasons customers give for buying
- The sales force: representatives, their quotas, their bonuses and commissions, and their territory assignments
- Sales territories and their commercial performance
- Special offers and discounts, and which products they apply to
- Currencies, currency exchange rates and the currencies in which each country/region trades
- Sales tax rates by state/province and transaction type
- Payment instruments (credit cards) and their association with people
- Online shopping cart activity

### 1.2 Out of scope but referenced

The sales area repeatedly refers to information that is maintained elsewhere in the operational system and is **not** part of this schema. These references must be preserved so the sales information can later be joined to those areas, but the source data itself is owned by other domains:

- **Products** — order lines, shopping cart items and special offers all reference a product; product master data (name, category, cost, colour, size) is not in this area.
- **People and business entities** — a customer, a sales representative and a credit-card holder are all identified by a business entity/person reference maintained in a person/HR area.
- **Employees** — a sales representative is an employee; employment attributes are held elsewhere.
- **Addresses** — billing and shipping addresses on an order are referenced, not held here.
- **Shipping methods** — an order names a shipping method that is defined elsewhere.
- **Countries/regions and states/provinces** — territories, currency assignments and tax rates all reference a geography master maintained elsewhere.

> **Clarification needed (C-01):** The boundary of the warehouse programme has not been agreed. This document covers only the sales area; whether products, people and geography are delivered in the same increment must be decided, because several sales reports (e.g. revenue by product category) cannot be produced from sales data alone.

---

## 2. Business entities

This section describes the things the business deals with in this area, how each is identified in business terms, and what the business needs to know about each.

### 2.1 Customer

The company recognises a single notion of "customer" that covers two quite different commercial relationships. A customer is either an **individual person** who buys directly, or a **reseller store** that buys from us to sell on. Every customer is assigned an account number by the accounting system, and every customer is located in a sales territory.

- **REQ-001** The business must be able to identify every customer by the **customer account number** assigned by the accounting system, which is described as uniquely identifying the customer.
- **REQ-002** The business must be able to distinguish an **individual-person customer** from a **store customer**, because the two are served, priced and reported on differently.
- **REQ-003** For an individual customer, the business must retain the reference to the **person** who is the customer.
- **REQ-004** For a store customer, the business must retain the reference to the **store**.
- **REQ-005** The business must know the **sales territory in which each customer is located**.
- **REQ-006** The business must know when a customer's record was last changed in the operating system, so that reporting can be reconciled against the source.
- **REQ-007** The business must be able to report the customer base by territory, and by customer kind (individual vs. store).

> **Clarification needed (C-02):** The schema allows a customer to carry either a person reference or a store reference. It does not state whether both may be populated at once, nor whether either may be absent. The business rule ("a customer is exactly one of person or store") needs to be confirmed with the sales operations team before reporting relies on it.

### 2.2 Store (reseller)

A store is a reseller business that buys from us. Stores are named businesses, are assigned a sales representative, and we hold a demographic profile of each one.

- **REQ-008** The business must be able to identify each **store by its business entity reference**, and must record its **store name**.
- **REQ-009** The business must know **which sales representative is assigned to each store**, since reseller relationships are managed by a named individual.
- **REQ-010** The business must retain the **store demographics** captured for each store. The schema describes this as covering the number of employees, annual sales and store type.
- **REQ-011** The business must be able to segment reseller performance by store demographic characteristics (e.g. store size or store type).

> **Clarification needed (C-03):** Store demographics are held in a structured document rather than as individual columns. The specific demographic attributes the business wants to report on must be listed explicitly, so they can be extracted; "annual sales", "number of employees" and "store type" are named in the schema description but the full set is not visible.

> **Clarification needed (C-04):** The schema describes the store identifier as a foreign key to the customer, while the customer also refers to the store. The direction of this relationship — and therefore whether every store is necessarily a customer — needs confirmation.

### 2.3 Sales order

A sales order is the central business event of this area. It is placed by a customer, it may be placed online by the customer or entered by a sales representative, it is fulfilled to a shipping address, and it carries the money.

- **REQ-012** The business must identify every order by its **sales order number**, which the schema describes as a unique sales order identification number.
- **REQ-013** The business must know **which customer placed each order**.
- **REQ-014** The business must know **whether the order was placed online by the customer or entered by a sales representative**, since this distinguishes the two sales channels.
- **REQ-015** For orders that were not placed online, the business must know **which sales representative created the order**.
- **REQ-016** The business must know **the territory in which each sale was made**. This is recorded on the order itself and is not necessarily the same as the customer's own territory or the representative's current territory — all three are held separately and reporting must be explicit about which is meant.
- **REQ-017** The business must track the **order lifecycle dates**: the date the order was created, the date it is due to the customer, and the date it was shipped.
- **REQ-018** The business must track the **current status of an order** using the operational status values: in process, approved, backordered, rejected, shipped, cancelled.
- **REQ-019** The business must be able to measure **order fulfilment performance**, i.e. whether orders shipped on or before their due date.
- **REQ-020** The business must retain the **customer's own purchase order number** where the customer supplied one, so that reseller enquiries can be answered in the customer's own terms.
- **REQ-021** The business must retain the **financial accounting number reference** carried on the order, to allow reconciliation with finance.
- **REQ-022** The business must know the **billing address** and the **shipping address** used for each order, as two separate pieces of information.
- **REQ-023** The business must know the **shipping method** chosen for each order.
- **REQ-024** The business must retain **sales representative comments** recorded against an order, as context for enquiries and disputes.
- **REQ-025** The business must be able to report **order counts and values by channel, by territory, by representative, by customer and by period**.

#### Order revisions

- **REQ-026** The business must track the **revision number** of an order, which the schema describes as an incremental number tracking changes to the order over time. The business needs to be able to tell that an order has been amended, and how many times.

> **Clarification needed (C-05):** The operational system holds only the current revision of an order, with a counter. It is not visible from the schema whether prior revisions are retained anywhere. If the business needs to see what an order looked like before it was amended, that requirement must be raised explicitly, because the source may not be able to answer it.

#### Order amounts

- **REQ-027** The business must record the **order subtotal**, described as the sum of the line totals for the order.
- **REQ-028** The business must record the **tax amount** charged on the order.
- **REQ-029** The business must record the **freight (shipping cost)** charged on the order.
- **REQ-030** The business must record the **total due from the customer**, described as subtotal plus tax plus freight.
- **REQ-031** The business must be able to analyse revenue with tax and freight separated from product revenue, since these are managed by different parts of the business.

#### Payment on an order

- **REQ-032** The business must know **which credit card was used** to pay for an order, where a card was used.
- **REQ-033** The business must retain the **credit card approval code** provided by the card company, for payment reconciliation and dispute handling.
- **REQ-034** The business must be able to report the share of orders paid by card versus those with no card recorded (e.g. reseller accounts on credit terms).

> **Clarification needed (C-06):** The schema does not describe any payment method other than credit card. How reseller orders are settled (invoice, credit terms) is not visible here and may sit in a finance system outside this area.

#### Currency on an order

- **REQ-035** The business must know **which currency exchange rate was applied to each order**, where the order was not in the company's base currency.
- **REQ-036** The business must be able to report sales both in the transaction currency and converted to a reporting currency, using the rate that applied to the order.

### 2.4 Sales order line

Each order is made up of one or more lines, each line being one product sold in a given quantity at a given price, optionally under a promotion.

- **REQ-037** The business must identify each **order line** within its order; the schema describes one incremental unique number per product sold.
- **REQ-038** The business must know **which product** was sold on each line.
- **REQ-039** The business must know the **quantity ordered per product**.
- **REQ-040** The business must know the **unit selling price** of the product on that line.
- **REQ-041** The business must know the **discount amount** applied to that line.
- **REQ-042** The business must know the **line total**, described as unit price × (1 − discount) × quantity.
- **REQ-043** The business must know **which special offer (promotional code) applied to each line**, so that promotional effectiveness can be measured.
- **REQ-044** The business must retain the **shipment tracking number supplied by the shipper** for each line, because lines of one order may ship separately.
- **REQ-045** The business must be able to analyse sales **by product, by quantity, by realised price and by discount level**.
- **REQ-046** The business must be able to distinguish **list-price revenue from discount given away**, at line level.

### 2.5 Sales reason

Customers may state one or more reasons for a purchase. Reasons are categorised.

- **REQ-047** The business must maintain the catalogue of **sales reasons**, each with a description and a **reason category** ("the category the sales reason belongs to").
- **REQ-048** The business must know **which sales reasons were recorded against each order**. An order may have several reasons, and a reason applies to many orders.
- **REQ-049** The business must be able to report **order volume and value by sales reason and by reason category** (e.g. promotion-driven vs. quality-driven purchases).
- **REQ-050** The business must be able to report the proportion of orders for which **no reason was recorded**, as a data-quality measure.

### 2.6 Sales representative

Sales representatives are employees who carry a quota, earn a bonus and a commission, and work a territory.

- **REQ-051** The business must identify each **sales representative** by their business entity reference, which is also their employee reference.
- **REQ-052** The business must know the **territory a representative is currently assigned to**.
- **REQ-053** The business must know each representative's **projected yearly sales quota**.
- **REQ-054** The business must know the **bonus due if the quota is met**.
- **REQ-055** The business must know the **commission percentage received per sale**.
- **REQ-056** The business must know the representative's **year-to-date sales total** and **previous-year sales total** as maintained by the operational system.
- **REQ-057** The business must be able to compare a representative's **actual sales against quota**, and identify who is on track to earn the bonus.
- **REQ-058** The business must be able to report **sales by representative over time**, independently of the running totals held in the operational system.

> **Clarification needed (C-07):** The year-to-date and last-year totals held against a representative are running figures maintained by the operational system. They may not agree with totals calculated from orders (for example, if cancelled or rejected orders are treated differently). The business must decide which figure is authoritative for performance reporting, and the two must be reconcilable.

> **Clarification needed (C-08):** Not every representative necessarily has a territory or a quota recorded. How representatives without a territory should appear in territory reporting needs a business rule.

### 2.7 Sales territory

Territories are the geographic organisation of the sales business. They roll up into larger geographic groups, sit within a country/region, and carry their own performance figures.

- **REQ-059** The business must maintain the catalogue of **sales territories**, each with a territory name.
- **REQ-060** The business must know the **country or region** each territory belongs to.
- **REQ-061** The business must know the **geographic group** a territory belongs to (the wider area above territory level), so that results can be rolled up regionally.
- **REQ-062** The business must know each territory's **year-to-date sales** and **previous-year sales**.
- **REQ-063** The business must know each territory's **year-to-date business costs** and **previous-year costs**.
- **REQ-064** The business must be able to report **territory contribution** — sales against costs — for the current and previous year.
- **REQ-065** The business must be able to roll territory results up to geographic group and to country/region.

> **Clarification needed (C-09):** As with representatives, the sales and cost totals held against a territory are running figures maintained operationally. Whether territory performance reporting should use these figures or figures recomputed from orders needs a decision (see C-07).

### 2.8 Credit card

- **REQ-066** The business must maintain the register of **credit cards** used for payment, identified by the card record held in the operational system.
- **REQ-067** The business must know the **card type (card name)**, the **card number**, and the **expiry month and year**.
- **REQ-068** The business must be able to report **sales by card type**.
- **REQ-069** Credit card numbers and expiry data are sensitive personal and payment information. Access must be restricted, and the business must state whether the card number is needed at all in the warehouse or whether a masked or partial value is sufficient.

### 2.9 Person-to-credit-card relationship

- **REQ-070** The business must know **which credit cards belong to which person**. A person may hold several cards, and the schema allows a card to be associated with more than one person.
- **REQ-071** The business must be able to identify **cards used on orders that are not registered to the ordering customer**, as an input to fraud and data-quality review.

### 2.10 Shopping cart activity

The online channel records products that shoppers have put into a cart, whether or not an order followed.

- **REQ-072** The business must retain **shopping cart items**, each identified within its shopping cart.
- **REQ-073** For each cart item, the business must know the **shopping cart identifier**, the **product**, the **quantity ordered**, and the **date and time the item was created**.
- **REQ-074** The business must be able to report **which products are added to carts**, and in what quantities.
- **REQ-075** The business must be able to measure **cart activity over time**, using the creation date of cart items.

> **Clarification needed (C-10):** The schema gives no link from a shopping cart to a customer, a session or a resulting sales order. Abandonment analysis ("carts that did not become orders") and per-customer cart analysis therefore **cannot** be answered from this area as it stands. If the business needs them, an additional source or an additional operational field is required. This should be raised explicitly rather than assumed.

> **Clarification needed (C-11):** It is not visible whether cart items are deleted once an order is placed. If they are, the warehouse will only ever see open carts, which materially changes what cart reporting can mean.

### 2.11 Special offer (promotion / discount)

Special offers are the company's promotions. They have a discount percentage, a type and a category, a validity period, and quantity thresholds.

- **REQ-076** The business must maintain the catalogue of **special offers**, each with a **discount description**.
- **REQ-077** The business must know each offer's **discount percentage**.
- **REQ-078** The business must know each offer's **discount type category**.
- **REQ-079** The business must know the **group the discount applies to**, described as e.g. Reseller or Customer, so that promotions can be reported per channel.
- **REQ-080** The business must know each offer's **minimum and maximum quantity** thresholds.
- **REQ-081** The business must know each offer's **start date and end date**, i.e. the period during which it is valid.
- **REQ-082** The business must be able to determine **which offers were valid at any given date**, including offers that have since expired, so that historical orders can be explained.
- **REQ-083** The business must be able to report **revenue and discount attributable to each special offer**, and to each offer type and category.

> **Clarification needed (C-12):** The minimum and maximum quantity fields are described in the source as "Minimum discount percent allowed" and "Maximum discount percent allowed", which contradicts their names and their placement. Their true business meaning must be confirmed before they are used in any rule or report.

### 2.12 Special offer applicability to products

- **REQ-084** The business must know **which products each special offer applies to**. An offer may cover many products, and a product may be covered by several offers.
- **REQ-085** The business must be able to check that the offer recorded on an order line was in fact **applicable to the product on that line**, as a data-quality and pricing-governance control.

### 2.13 Currency

- **REQ-086** The business must maintain the list of **currencies**, identified by their **ISO currency code**, with the **currency name**.
- **REQ-087** The business must be able to present currency names in reporting rather than raw codes.

### 2.14 Currency exchange rate

Exchange rates are captured per day and per currency pair, with both an average and an end-of-day value.

- **REQ-088** The business must retain **exchange rates as a time series**: for each rate, the **date and time the rate was obtained**, the **currency converted from**, and the **currency converted to**.
- **REQ-089** The business must retain both the **average exchange rate for the day** and the **final (end-of-day) rate**, as these serve different reporting purposes.
- **REQ-090** The business must be able to reproduce **the rate that was actually applied to a given order**, not merely today's rate, so that historical reporting is stable and does not change when rates move.
- **REQ-091** The business must be able to report **the same sales figures in more than one currency**, and must state which of the two rates (average or end-of-day) is used for each report.
- **REQ-092** The business must be able to identify orders **where no exchange rate was recorded** and understand how those are to be treated (presumed base currency).

### 2.15 Country/region trading currency

- **REQ-093** The business must know **which currencies are used in which countries/regions**. A country/region may be associated with more than one currency, and a currency with more than one country/region.
- **REQ-094** The business must be able to check that sales in a given country/region were transacted in a currency valid for that country/region.

### 2.16 Sales tax rate

- **REQ-095** The business must maintain the register of **sales tax rates**, each with a **tax rate description**.
- **REQ-096** The business must know the **state, province or country/region each tax rate applies to**.
- **REQ-097** The business must know the **tax type** for each rate, using the operational meanings: applied to retail transactions, applied to wholesale transactions, or applied to all sales.
- **REQ-098** The business must know the **tax rate amount**.
- **REQ-099** The business must be able to report **tax collected by jurisdiction and by tax type**.
- **REQ-100** The business must be able to compare the **tax amount charged on an order** with the tax rates applicable to the relevant jurisdiction, as a compliance check.

> **Clarification needed (C-13):** The tax rate table has no validity period. It therefore records the rates as they stand now, not the rate that applied when a historical order was taxed. If the business needs to explain historical tax amounts, the warehouse must capture rate changes as they occur going forward; it cannot recover past rates from this source.

---

## 3. How the entities relate

Stated in business terms, ignoring technical keys:

- **REQ-101** A **sales order is placed by exactly one customer**, and a customer may place many orders over time.
- **REQ-102** A **sales order is handled by at most one sales representative** — orders placed online by the customer have no representative — and a representative handles many orders.
- **REQ-103** A **sales order is made in one sales territory**; a territory carries many orders.
- **REQ-104** A **sales order consists of one or more order lines**, and each order line belongs to exactly one order.
- **REQ-105** An **order line sells one product**; a product is sold on many order lines.
- **REQ-106** An **order line may be sold under one special offer**; an offer is used on many order lines.
- **REQ-107** A **sales order may cite several sales reasons**, and a sales reason may be cited on many orders.
- **REQ-108** A **sales order may be paid with one credit card**; a card may be used on many orders.
- **REQ-109** A **credit card may be registered to one or more people**, and a person may hold several cards.
- **REQ-110** A **sales order may use one currency exchange rate**; a rate may apply to many orders.
- **REQ-111** A **customer is located in one sales territory**; a territory contains many customers.
- **REQ-112** A **customer is either a person or a store** (see C-02).
- **REQ-113** A **reseller store is served by one sales representative**; a representative serves many stores.
- **REQ-114** A **sales representative is currently assigned to at most one territory**, and has worked a series of territories over time (see §4).
- **REQ-115** A **sales territory belongs to one country/region and to one geographic group**.
- **REQ-116** A **special offer applies to one or more products**, and a product may be covered by several offers.
- **REQ-117** A **country/region may trade in several currencies**, and a currency may be used in several countries/regions.
- **REQ-118** An **exchange rate converts from one currency to another** on a given day.
- **REQ-119** A **sales tax rate applies to one state/province or country/region** for a given tax type.
- **REQ-120** A **shopping cart contains one or more cart items**, each for one product. There is no recorded link from a cart to a customer or to an order (see C-10).
- **REQ-121** A **sales order carries a billing address and a shipping address**, which may differ.
- **REQ-122** A **sales order is shipped using one shipping method**.

---

## 4. Information that changes over time

Several parts of this area are explicitly historical, and the business must be able to answer "what was true then", not only "what is true now".

### 4.1 Sales quota history

- **REQ-123** The business must retain the **full history of sales quotas per representative**, with the **quota date** and the **quota amount** in force from that date.
- **REQ-124** The business must be able to determine **the quota that applied to a representative at any point in the past**, and compare it to the sales actually achieved in that period.
- **REQ-125** The business must be able to report **how a representative's quota has moved over time**, and how often it was revised.
- **REQ-126** The business must be aware that the representative record also carries a **single current quota figure**, alongside the dated history. Reporting must state which of the two it uses; the two must be reconcilable.

### 4.2 Territory assignment history

- **REQ-127** The business must retain the **history of which representative worked which territory**, with the **date the representative started work in the territory** and the **date they left**.
- **REQ-128** A representative's assignment is **open-ended while they are still working the territory** (no end date recorded); the business must be able to identify the currently active assignment for each representative.
- **REQ-129** The business must be able to determine **who was responsible for a territory on any given date**, so that historical sales can be credited to the person who actually held the territory at the time.
- **REQ-130** The business must be able to see the **sequence of representatives who have held a territory**, and how long each held it.
- **REQ-131** The business must be aware that the representative record also carries the **territory currently assigned**, alongside the dated history — the same current-versus-historical duality as the quota (see REQ-126).
- **REQ-132** Where an order's territory differs from the representative's territory at the time of the order, the business must be able to see and explain that difference (see REQ-016).

> **Clarification needed (C-14):** It is not visible from the schema whether a representative may hold two territories simultaneously, or whether assignment periods are guaranteed not to overlap. This affects how territory-based credit is calculated and needs a business rule.

### 4.3 Currency rates

- **REQ-133** Exchange rates are, by their nature, a **daily time series**; the business needs the rate as at the relevant date, and rates must never be retrospectively overwritten in reporting (see REQ-090).

### 4.4 Promotion validity

- **REQ-134** Special offers have **explicit start and end dates**; the business must be able to determine the offers that were live at any date, including expired ones (see REQ-082).

### 4.5 Slowly changing descriptive information

- **REQ-135** The business must be able to see how **descriptive information changes over time** where it matters commercially — in particular a customer's territory, a store's assigned representative, a store's demographics, a special offer's discount percentage, and a territory's group.
- **REQ-136** Every record in this area carries a **"last modified" date and time**. The business needs this as the primary signal that something has changed, and as the basis for reconciling warehouse content with the operational system.
- **REQ-137** For all other entities in this area, the operational system holds only the **current state**. The business must accept that history for those entities can only be built from the point the warehouse starts capturing it, and must decide for which of them that is worth doing.

> **Clarification needed (C-15):** The business has not yet stated how far back history is required, or how frequently the sales data must be refreshed (daily, intra-day). Both materially affect what can be delivered.

---

## 5. Cross-cutting business requirements

### 5.1 Analysis the business expects to perform

- **REQ-138** Report **sales value and volume** by period, territory, geographic group, country/region, representative, customer, customer kind, product, channel, currency, special offer and sales reason.
- **REQ-139** Compare **actual sales against quota** per representative and per period, including the bonus and commission implications.
- **REQ-140** Report **territory profitability** using sales and cost figures at territory level.
- **REQ-141** Measure **discounting**: total discount given, by offer, by product, by channel and by customer kind.
- **REQ-142** Measure **fulfilment**: order-to-ship elapsed time, on-time-against-due-date performance, and the distribution of order statuses.
- **REQ-143** Measure **channel mix**: online orders versus representative-entered orders, in volume and value.
- **REQ-144** Report **tax and freight** separately from product revenue.
- **REQ-145** Report **sales in a single reporting currency** across all territories, using the rate that applied to each order.
- **REQ-146** Analyse the **reseller base** by store demographics and by assigned representative.
- **REQ-147** Analyse **online cart activity** by product and period, within the limits noted in C-10.

### 5.2 Data quality and governance

- **REQ-148** The business must be able to see, for each order, whether the **key commercial attributes are present**: customer, territory, representative (where not online), currency rate (where non-base currency), and payment reference.
- **REQ-149** The business must be able to check that the **order total agrees with the sum of its lines plus tax and freight**, and to report where it does not.
- **REQ-150** The business must be able to check that **line totals agree with quantity, unit price and discount** as described by the source.
- **REQ-151** The business must be able to report **orders referencing a special offer that is outside its validity period** at the order date.
- **REQ-152** The business must be able to report **customers that are neither a person nor a store**, or that are both, once C-02 is resolved.
- **REQ-153** The business must be able to report **representatives with no territory**, and **territories with no representative**, on any given date.
- **REQ-154** The business must be able to reconcile **operationally maintained running totals** (representative and territory year-to-date and last-year figures) against totals recalculated from orders, and to report material differences (see C-07, C-09).
- **REQ-155** Each entity in this area has a named business owner who is accountable for its definitions and for resolving the clarifications in this document. The owners have not yet been assigned and must be, before the warehouse is built.

### 5.3 Privacy and sensitivity

- **REQ-156** **Credit card data** (card number, expiry, card type, holder association) is payment-sensitive. Its handling, retention and access rules must be defined before it is loaded (see REQ-069).
- **REQ-157** **Individual customers are natural persons**. Personal-data handling rules — including retention limits and the treatment of deletion requests — must be defined for the customer information in this area.
- **REQ-158** **Sales representative quota, bonus, commission and achievement** figures are effectively remuneration data about identifiable individuals and must be access-restricted to those with a legitimate need.
- **REQ-159** **Store demographics** are commercially sensitive information about our reseller partners and must be treated as confidential.

### 5.4 Traceability and technical notes

- **REQ-160** Several records carry a **replication identifier** described in the source as supporting a merge-replication sample. It has no business meaning; the business does not require it, but it may be retained as a technical trace of the source record.
- **REQ-161** Some order and customer values are described as **computed by the operational system** (the order number, the customer account number, the line total, the order subtotal and the total due). The business expects these to be taken as given from the source rather than recalculated, but expects them to be **checkable** (see REQ-149, REQ-150).

---

## 6. Open points summary

| Ref | Open point |
|---|---|
| C-01 | Programme boundary — whether product, person and geography areas are delivered alongside sales |
| C-02 | Whether a customer is always exactly one of person or store |
| C-03 | Which store demographic attributes are actually required for reporting |
| C-04 | Direction of the store-to-customer relationship; whether every store is a customer |
| C-05 | Whether prior order revisions are retained anywhere in the source |
| C-06 | How non-card payments (reseller credit terms) are recorded, if at all |
| C-07 | Whether representative year-to-date/last-year totals or recalculated order totals are authoritative |
| C-08 | Treatment of representatives without a territory or quota |
| C-09 | Whether territory running totals or recalculated totals are authoritative |
| C-10 | No link from shopping cart to customer or order — abandonment analysis not answerable today |
| C-11 | Whether cart items survive after an order is placed |
| C-12 | Contradictory meaning of the special offer minimum/maximum quantity fields |
| C-13 | Sales tax rates carry no validity period — historical tax rates not recoverable |
| C-14 | Whether representative territory assignments may overlap |
| C-15 | Required history depth and refresh frequency |
