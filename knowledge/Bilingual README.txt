======================================
Table: BOOKING
表：预订
book_id — Unique identifier for each booking
book_id — 每个预订的唯一标识符

book_gold_price — Gold price at the time of booking
book_gold_price — 预订时的黄金价格

book_labor_price — Labor cost associated with the booking
book_labor_price — 与预订相关的人工成本

book_price — Total price of the booking (gold + labor)
book_price — 预订的总价（黄金 + 人工）

book_remaining — Remaining balance or unpaid amount for the booking
book_remaining — 预订的剩余余额或未付金额

book_date — Date when the booking was made
book_date — 预订的日期

book_last_update — Last updated timestamp of the booking record
book_last_update — 预订记录的最后更新时间

book_created_at — Timestamp of when the booking was first created
book_created_at — 预订记录首次创建的时间戳

book_cust_id — Reference to the customer ID who made the booking
book_cust_id — 预订客户的ID引用

book_weight — Weight of the gold item booked (in grams)
book_weight — 预订的黄金重量（克）

book_receipt_no — Receipt number linked to the booking
book_receipt_no — 与预订相关的收据号码

book_status — Current status of the booking (e.g., BOOKED, COMPLETED)
book_status — 预订的当前状态（例如：已预订、已完成）

======================================
Table: BOOK PAYMENT
表：预订付款
bp_id — Unique identifier for each book payment record
bp_id — 每个预订付款记录的唯一标识符

bp_payment — Payment amount made by the customer
bp_payment — 客户支付的金额

bp_payment_date — Date when the payment was made
bp_payment_date — 付款日期

bp_book_id — Reference to the associated booking (book_id)
bp_book_id — 关联预订的引用（book_id）

bp_created_at — Timestamp of when the payment record was created
bp_created_at — 付款记录的创建时间戳

bp_status — Status of the payment — either PAID or CANCELLED
bp_status — 付款状态 — 已支付或已取消

bp_last_update — Timestamp of the last update to this payment record
bp_last_update — 付款记录最后更新时间戳

======================================
Table: CATEGORY PATTERN MAPPING
表：类别图案映射
cpat_id — Unique identifier for each category-pattern mapping
cpat_id — 每个类别与图案映射的唯一标识符

cpat_category — Category name or ID that the pattern is linked to
cpat_category — 图案所关联的类别名称或ID

cpat_pattern — Pattern name or ID being mapped to the category
cpat_pattern — 映射到类别的图案名称或ID

cpat_image_path — File path or URL of the image representing the pattern
cpat_image_path — 表示该图案的图片路径或URL

cpat_created_at — Timestamp when the mapping record was first created
cpat_created_at — 映射记录首次创建的时间戳

cpat_last_update — Timestamp of the most recent update to this mapping
cpat_last_update — 映射记录最近一次更新时间戳

======================================
Table: CUSTOMER
表：客户
cust_id — Unique identifier for each customer
cust_id — 每个客户的唯一标识符

cust_email_address — Customer's email address
cust_email_address — 客户的电子邮件地址

cust_phone_number — Customer's contact phone number
cust_phone_number — 客户的联系电话

cust_address — Full address of the customer
cust_address — 客户的完整地址

cust_last_update — Timestamp of the most recent update to the customer record
cust_last_update — 客户记录最近一次更新时间戳

cust_created_at — Timestamp when the customer record was first created
cust_created_at — 客户记录首次创建的时间戳

cust_buyer_id — Internal buyer ID (e-invoice related)
cust_buyer_id — 内部买方ID（电子发票相关）

cust_sst_reg_no — SST registration number (e-invoice related)
cust_sst_reg_no — SST注册号码（电子发票相关）

cust_tin — Tax Identification Number (TIN) of the customer (e-invoice related)
cust_tin — 客户的税号（TIN）（电子发票相关）

cust_name — Full name of the customer
cust_name — 客户的全名

======================================
Table: PURCHASE
表：采购
pur_id — Unique identifier for each purchase record
pur_id — 每个采购记录的唯一标识符

pur_slm_id — Reference to the salesman ID from whom the stock is purchased
pur_slm_id — 采购库存的销售员ID引用

pur_gold_cost — Total gold cost of the purchase
pur_gold_cost — 采购的黄金总成本

pur_labor_cost — Total labor cost of the purchase
pur_labor_cost — 采购的人工总成本

pur_method — Purchase method: either CASH or TRADE-IN
pur_method — 采购方式：现金或以旧换新

pur_official_invoice — Indicates whether there is an official invoice: 1 (Yes) or 0 (No)
pur_official_invoice — 是否有正式发票：1（是）或0（否）

pur_date — Date when the stock was purchased
pur_date — 采购日期

pur_billing_date — Date when the billing to the salesman was completed
pur_billing_date — 对销售员结算完成的日期

pur_weight — Total weight of the purchase in grams
pur_weight — 采购总重量（克）

pur_invoice_no — Invoice number associated with the purchase
pur_invoice_no — 采购的发票号码

pur_last_update — Timestamp of the most recent update to the purchase record
pur_last_update — 采购记录最近一次更新时间戳

pur_created_at — Timestamp when the purchase record was first created
pur_created_at — 采购记录首次创建的时间戳

pur_total_trade_in_amt — Total value of items traded in during the purchase
pur_total_trade_in_amt — 采购中以旧换新的总价值

pur_total_cash_amt — Total cash paid during the purchase
pur_total_cash_amt — 采购支付的现金总额

pur_total_amt — Overall total amount for the purchase (cash + trade-in)
pur_total_amt — 采购的总金额（现金 + 以旧换新）

pur_payment_status — Current payment status: NOT_PAID, IN_PAYMENT, PAID, or CANCELLED
pur_payment_status — 当前付款状态：未付款、付款中、已付款或已取消

pur_code — Custom purchase code in the format MMYY+SalesmanShortName (e.g., 0111MG)
pur_code — 自定义采购编码，格式为MMYY+销售员简称（例如：0111MG）


======================================
Table: SALE
表：销售
sale_id — Unique identifier for each sale transaction
sale_id — 每个销售交易的唯一标识符

sale_receipt_no — Receipt number associated with the sale
sale_receipt_no — 与销售相关的收据号码

sale_cust_id — Reference to the customer ID who made the purchase
sale_cust_id — 购买客户的ID引用

sale_sold_date — Date when the sale was made
sale_sold_date — 销售日期

sale_labor_sell — Labor charge included in the sale
sale_labor_sell — 销售中包含的人工费用

sale_gold_sell — Gold cost included in the sale
sale_gold_sell — 销售中包含的黄金成本

sale_price — Total price of the sale (labor + gold)
sale_price — 销售总价（人工 + 黄金）

sale_last_update — Timestamp of the most recent update to the sale record
sale_last_update — 销售记录最近一次更新时间戳

sale_weight — Weight of the gold item sold (in grams)
sale_weight — 销售黄金重量（克）

sale_created_at — Timestamp when the sale record was created
sale_created_at — 销售记录创建时间戳

sale_official_receipt — Indicates whether an official receipt was issued: 1 (Yes) or 0 (No)
sale_official_receipt — 是否已开具正式收据：1（是）或0（否）

======================================
Table: SALESMAN
表：销售员
slm_id — Unique identifier for each salesman
slm_id — 每个销售员的唯一标识符

slm_email_address — Salesman’s email address
slm_email_address — 销售员的电子邮件地址

slm_phone_number — Salesman’s contact phone number
slm_phone_number — 销售员的联系电话

slm_company_name — Name of the company the salesman represents
slm_company_name — 销售员所属公司的名称

slm_last_update — Timestamp of the most recent update to the salesman record
slm_last_update — 销售员记录最近一次更新时间戳

slm_created_at — Timestamp when the salesman record was first created
slm_created_at — 销售员记录首次创建时间戳

slm_supplier_id — Reference to the supplier ID (e-invoice related)
slm_supplier_id — 供应商ID引用（电子发票相关）

slm_tin — Tax Identification Number of the salesman (e-invoice related)
slm_tin — 销售员的税号（电子发票相关）

slm_reg_no — Business registration number (e-invoice related)
slm_reg_no — 商业注册号（电子发票相关）

slm_msic — Malaysian Standard Industrial Classification (MSIC) code (e-invoice related)
slm_msic — 马来西亚标准行业分类代码（电子发票相关）

slm_desc — Additional description or notes about the salesman
slm_desc — 关于销售员的额外描述或备注

slm_address — Full address of the salesman
slm_address — 销售员的完整地址

slm_name — Full name of the salesman
slm_name — 销售员的全名

======================================
Table: STOCK
表：库存
stk_id — Unique identifier for each stock item
stk_id — 每个库存物品的唯一标识符

stk_type — Type of stock item; one of: NECKLACE, RING, BRACELET, BANGLE, EARING, PENDANT, ANKLET
stk_type — 库存物品类型；包括：项链、戒指、手链、手镯、耳环、吊坠、脚链

stk_weight — Weight of the stock item in grams
stk_weight — 库存物品重量（克）

stk_size — Size of the item (applicable only for BANGLE and RING)
stk_size — 物品尺寸（仅适用于手镯和戒指）

stk_length — Length of the item (applicable only for NECKLACE, BRACELET, ANKLET)
stk_length — 物品长度（仅适用于项链、手链、脚链）

stk_labor_cost — Labor cost associated with the stock item
stk_labor_cost — 库存物品的人工成本

stk_labor_sell — Labor price when selling the stock
stk_labor_sell — 销售时的人工价格

stk_pur_date — Date when the stock was purchased
stk_pur_date — 采购日期

stk_sell_date — Date when the stock was sold
stk_sell_date — 销售日期

stk_gold_cost — Gold cost price of the stock
stk_gold_cost — 库存黄金成本价

stk_gold_sell — Gold price when selling the stock
stk_gold_sell — 销售时的黄金价格

stk_status — Current status of the stock item; one of: IN STOCK, SOLD, BOOKED, CANCELLED
stk_status — 库存物品当前状态；包括：在库、已售、已预订、已取消

stk_profit — Profit made on the stock item
stk_profit — 库存物品利润

stk_pattern — Pattern associated with the stock item
stk_pattern — 与库存物品关联的图案

stk_gold_type — Gold purity of the stock (e.g., 916, 999)
stk_gold_type — 黄金纯度（例如：916、999）

stk_last_update — Timestamp of the most recent update to the stock record
stk_last_update — 库存记录最近一次更新时间戳

stk_pur_id — Reference to the purchase record ID
stk_pur_id — 采购记录ID引用

stk_created_at — Timestamp when the stock record was first created
stk_created_at — 库存记录首次创建时间戳

stk_sale_id — Reference to the sale record ID
stk_sale_id — 销售记录ID引用

stk_book_id — Reference to the booking record ID
stk_book_id — 预订记录ID引用

stk_returned — Indicates if the stock was returned: 1 (Yes) or 0 (No)
stk_returned — 是否退货：1（是）或0（否）

stk_barcode — Barcode generated for the stock item
stk_barcode — 库存物品的条形码

stk_remark — Internal remarks or notes about the stock item
stk_remark — 库存物品的内部备注

stk_tag — Tags assigned to the stock, separated by semicolons (e.g., 2C; 2 BUTTERFLY)
stk_tag — 库存物品标签，用分号分隔（例如：2C; 2 BUTTERFLY）

stk_weight_sell — Weight used for selling purposes
stk_weight_sell — 用于销售的重量

stk_weight_book — Weight used for booking purposes
stk_weight_book — 用于预订的重量

stk_labor_book — Labor cost used for booking
stk_labor_book — 预订使用的人工成本

stk_gold_book — Gold cost used for booking
stk_gold_book — 预订使用的黄金成本

stk_book_price — Booking price of the stock
stk_book_price — 库存的预订价格

stk_printed — Indicates whether the barcode is printed: 1 (Yes) or 0 (No)
stk_printed — 是否已打印条码：1（是）或0（否）