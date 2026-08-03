
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <title>Motor Insurance Quotation</title>

  <!--
    PURPOSE
    -------
    A semantic, print-ready HTML representation of the supplied motor-insurance
    quotation design.

    HOW TO USE
    ----------
    1. Replace the sample text inside elements that have a data-field attribute.
    2. Replace the text-based brand marks with real <img> tags when logo files exist.
    3. Print from Chromium/Playwright with "Background graphics" enabled.
    4. Preferred PDF size: A4 portrait, margins: none.

    AI-FRIENDLY STRUCTURE
    ---------------------
    Every important region has:
      - a data-section attribute
      - descriptive HTML headings
      - data-field keys for dynamic values
      - a machine-readable JSON document map at the bottom
  -->

  <style>
    :root {
      --page-width: 210mm;
      --page-height: 297mm;
      --page-padding-x: 11.5mm;
      --page-padding-y: 10mm;

      --ink: #151d2a;
      --ink-soft: #465064;
      --muted: #7e8797;
      --line: #d6dbe2;
      --line-strong: #bec6d1;
      --panel: #ffffff;
      --panel-soft: #fafbfc;
      --heading: #1f2835;
      --accent: #ee1f2a;
      --accent-dark: #c9101d;
      --success: #098d46;

      --radius-sm: 2.5mm;
      --radius-md: 3.2mm;
      --shadow: 0 2mm 7mm rgba(22, 33, 49, 0.10);
    }

    * {
      box-sizing: border-box;
    }

    html,
    body {
      margin: 0;
      padding: 0;
      color: var(--ink);
      background: #eef0f3;
      font-family:
        Arial,
        "Helvetica Neue",
        "Noto Sans",
        "Noto Sans CJK SC",
        sans-serif;
      font-size: 10pt;
      line-height: 1.25;
    }

    body {
      padding: 12mm 0;
    }

    .quotation-page {
      width: var(--page-width);
      min-height: var(--page-height);
      margin: 0 auto;
      padding:
        var(--page-padding-y)
        var(--page-padding-x)
        8mm;
      background: #fff;
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    /* ------------------------------
       Shared typography and helpers
       ------------------------------ */

    h1,
    h2,
    h3,
    p {
      margin: 0;
    }

    .muted {
      color: var(--muted);
    }

    .strong {
      font-weight: 700;
    }

    .nowrap {
      white-space: nowrap;
    }

    .visually-hidden {
      position: absolute !important;
      width: 1px !important;
      height: 1px !important;
      padding: 0 !important;
      margin: -1px !important;
      overflow: hidden !important;
      clip: rect(0, 0, 0, 0) !important;
      border: 0 !important;
      white-space: nowrap !important;
    }

    [data-section] {
      break-inside: avoid;
      page-break-inside: avoid;
    }

    /* ------------------------------
       Document header
       ------------------------------ */

    .document-header {
      display: grid;
      grid-template-columns: 1.25fr 0.9fr 1.15fr;
      align-items: end;
      gap: 5mm;
      min-height: 25mm;
      padding-bottom: 3.6mm;
      border-bottom: 0.35mm solid #8f9baa;
    }

    .agency-brand {
      display: flex;
      align-items: center;
      gap: 2.6mm;
      min-width: 0;
    }

    .agency-shield {
      position: relative;
      display: grid;
      place-items: center;
      width: 11mm;
      height: 13mm;
      flex: 0 0 auto;
      color: #fff;
      background: var(--accent);
      clip-path: polygon(50% 0%, 92% 12%, 92% 58%, 76% 79%, 50% 100%, 24% 79%, 8% 58%, 8% 12%);
    }

    .agency-shield::before {
      content: "";
      width: 5mm;
      height: 7mm;
      border: 1.2mm solid #fff;
      border-top-width: 1.5mm;
      clip-path: polygon(0 0, 100% 0, 100% 70%, 50% 100%, 0 70%);
    }

    .agency-name {
      font-size: 18pt;
      font-weight: 900;
      line-height: 0.95;
      letter-spacing: -0.45pt;
    }

    .agency-tagline {
      margin-top: 1mm;
      font-size: 7.5pt;
      color: #111;
    }

    .insurer-brand {
      justify-self: center;
      text-align: center;
    }

    .insurer-symbol {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 1mm;
      margin-bottom: 1.2mm;
    }

    .insurer-loop {
      width: 9mm;
      height: 7mm;
      border: 2.1mm solid var(--accent);
      border-radius: 7mm 7mm 2mm 7mm;
      transform: rotate(2deg);
    }

    .insurer-loop:last-child {
      transform: scaleX(-1) rotate(2deg);
    }

    .insurer-name {
      display: inline-block;
      padding: 1.4mm 3mm 1.6mm;
      color: #fff;
      background: var(--accent);
      font-size: 15.5pt;
      line-height: 1;
    }

    .quotation-reference {
      justify-self: end;
      padding-bottom: 1.4mm;
      font-size: 10.4pt;
      color: var(--ink-soft);
    }

    .quotation-reference [data-field] {
      color: #a5acb8;
    }

    /* ------------------------------
       Main title
       ------------------------------ */

    .title-row {
      padding: 5.2mm 0 4.8mm;
    }

    .title-row h1 {
      font-size: 22pt;
      line-height: 1;
      letter-spacing: -0.5pt;
    }

    .title-row .accent-word {
      color: var(--accent);
      font-style: italic;
      font-weight: 800;
    }

    /* ------------------------------
       Generic panel styles
       ------------------------------ */

    .panel {
      border: 0.28mm solid var(--line);
      border-radius: var(--radius-md);
      background: var(--panel);
      overflow: hidden;
    }

    .panel-heading {
      padding: 2.4mm 3.8mm;
      color: #fff;
      background: var(--heading);
      font-size: 11.3pt;
      font-weight: 800;
      letter-spacing: 0.1pt;
    }

    /* ------------------------------
       Coverage and payment area
       ------------------------------ */

    .summary-grid {
      display: grid;
      grid-template-columns: minmax(0, 2.28fr) minmax(51mm, 1fr);
      gap: 3.6mm;
      align-items: stretch;
    }

    .coverage-panel {
      min-width: 0;
    }

    .coverage-content {
      padding: 2.3mm 3.8mm 1.7mm;
    }

    .coverage-table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 10pt;
    }

    .coverage-table col:nth-child(1) {
      width: 43%;
    }

    .coverage-table col:nth-child(2) {
      width: 20%;
    }

    .coverage-table col:nth-child(3) {
      width: 37%;
    }

    .coverage-table th,
    .coverage-table td {
      height: 7.2mm;
      padding: 1.2mm 0;
      vertical-align: middle;
      text-align: left;
    }

    .coverage-table th {
      padding-right: 2mm;
      font-weight: 400;
    }

    .coverage-table td {
      color: var(--ink-soft);
    }

    .coverage-table tr.money-row th,
    .coverage-table tr.money-row td {
      border-top: 0.23mm solid #e3e6eb;
    }

    .coverage-table tr.total-row th,
    .coverage-table tr.total-row td {
      height: 6.7mm;
      border-top: 0.32mm solid var(--line-strong);
      font-weight: 800;
      color: var(--ink);
    }

    .currency {
      text-align: center !important;
      color: var(--ink) !important;
    }

    .amount {
      text-align: right !important;
      padding-right: 1mm !important;
      color: var(--ink) !important;
      font-variant-numeric: tabular-nums;
    }

    .payment-card {
      padding: 3.5mm 4mm;
      border: 0.28mm solid var(--line);
      border-radius: var(--radius-md);
      background: #fff;
    }

    .payment-title {
      margin-bottom: 4mm;
      font-size: 11.2pt;
      font-weight: 400;
    }

    .bank-brand {
      display: flex;
      align-items: center;
      gap: 2.4mm;
      margin-bottom: 5mm;
    }

    .bank-mark {
      position: relative;
      width: 11mm;
      height: 9mm;
      flex: 0 0 auto;
    }

    .bank-mark::before,
    .bank-mark::after {
      content: "";
      position: absolute;
      left: 1mm;
      width: 8mm;
      height: 1.4mm;
      border-radius: 2mm;
      transform: rotate(38deg);
    }

    .bank-mark::before {
      top: 2mm;
      background: #002f6c;
      box-shadow:
        0 2.2mm 0 #002f6c,
        0 4.4mm 0 #ed1c24;
    }

    .bank-mark::after {
      top: 0.2mm;
      left: 3.1mm;
      width: 6.2mm;
      background: #ed1c24;
    }

    .bank-name {
      color: #001c52;
      font-size: 14.2pt;
      font-weight: 800;
      letter-spacing: -0.35pt;
    }

    .bank-details-label {
      margin-bottom: 2.1mm;
      font-size: 10.4pt;
    }

    .bank-account {
      margin-bottom: 3.8mm;
      color: var(--ink-soft);
      font-size: 10.4pt;
      font-variant-numeric: tabular-nums;
    }

    .payee-name {
      margin-bottom: 1.5mm;
      font-size: 10.4pt;
      font-weight: 800;
    }

    .bank-branch {
      padding-bottom: 3.5mm;
      color: var(--ink-soft);
      border-bottom: 0.25mm solid var(--line);
    }

    .driver-row {
      display: flex;
      align-items: center;
      gap: 3.7mm;
      padding-top: 3.3mm;
      font-size: 11.1pt;
    }

    .driver-icon {
      position: relative;
      display: grid;
      place-items: center;
      width: 11mm;
      height: 10mm;
      flex: 0 0 auto;
      border: 1.1mm solid #111;
      border-radius: 1mm;
    }

    .driver-icon::before {
      content: "";
      width: 3.2mm;
      height: 3.2mm;
      border: 0.8mm solid #111;
      border-radius: 50%;
      transform: translateY(-1.2mm);
    }

    .driver-icon::after {
      content: "";
      position: absolute;
      bottom: 0.7mm;
      width: 6.5mm;
      height: 3.2mm;
      border: 0.8mm solid #111;
      border-bottom: 0;
      border-radius: 4mm 4mm 0 0;
      background: #fff;
    }

    /* ------------------------------
       Benefit sections
       ------------------------------ */

    .benefit-section {
      margin-top: 4mm;
    }

    .benefit-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 3.1mm 3.5mm;
      padding: 3.2mm;
    }

    .benefit-card {
      display: grid;
      grid-template-columns: 10.5mm minmax(0, 1fr);
      align-items: center;
      min-height: 13.8mm;
      padding: 1.5mm 2mm;
      border: 0.25mm solid var(--line);
      border-radius: var(--radius-sm);
      background: #fff;
      overflow: hidden;
    }

    .benefit-card.with-brand {
      grid-template-columns: 10.5mm minmax(0, 1fr) auto;
    }

    .benefit-icon {
      display: grid;
      place-items: center;
      width: 8.7mm;
      height: 8.7mm;
      color: #fff;
      background: var(--heading);
      border-radius: 1.4mm;
      font-size: 5.7pt;
      font-weight: 900;
      line-height: 1;
      letter-spacing: -0.2pt;
    }

    .benefit-copy {
      min-width: 0;
    }

    .benefit-title {
      overflow: hidden;
      color: var(--ink);
      font-size: 10.1pt;
      line-height: 1.15;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .benefit-subtitle {
      margin-top: 1mm;
      overflow: hidden;
      color: var(--ink-soft);
      font-size: 8.3pt;
      line-height: 1.1;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .partner-wordmark {
      padding-left: 2mm;
      color: var(--success);
      font-size: 18pt;
      line-height: 1;
      letter-spacing: -1.6pt;
    }

    /* ------------------------------
       Footer
       ------------------------------ */

    .document-footer {
      display: flex;
      align-items: baseline;
      gap: 2mm;
      margin-top: 4.5mm;
      color: var(--ink-soft);
      font-size: 9pt;
    }

    .footer-separator {
      color: #8993a2;
    }

    /* ------------------------------
       Print behavior
       ------------------------------ */

    @page {
      size: A4 portrait;
      margin: 0;
    }

    @media print {
      html,
      body {
        width: var(--page-width);
        height: var(--page-height);
        background: #fff;
      }

      body {
        padding: 0;
      }

      .quotation-page {
        margin: 0;
        box-shadow: none;
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
      }
    }

    /* Optional reduced scaling for printers with slightly different font metrics. */
    @media print and (max-height: 296mm) {
      .quotation-page {
        transform-origin: top left;
      }
    }
  </style>
</head>

<body>
  <main
    class="quotation-page"
    data-document-type="motor-insurance-quotation"
    aria-labelledby="quotation-title"
  >
    <!-- =========================================================
         SECTION 1: HEADER / BRANDING
         ========================================================= -->
    <header class="document-header" data-section="document-header">
      <section class="agency-brand" aria-label="Issuing insurance agency">
        <span class="agency-shield" aria-hidden="true"></span>

        <div>
          <div class="agency-name" data-field="agency.name">RISKLOCKER</div>
          <div class="agency-tagline" data-field="agency.tagline">
            Commercial Insurance Agency
          </div>
        </div>
      </section>

      <section class="insurer-brand" aria-label="Insurance provider">
        <div class="insurer-symbol" aria-hidden="true">
          <span class="insurer-loop"></span>
          <span class="insurer-loop"></span>
        </div>

        <div class="insurer-name" data-field="insurer.name">
          AmAssurance
        </div>
      </section>

      <p class="quotation-reference">
        Quotation Ref:
        <span data-field="quotation.reference">XCX000X</span>
      </p>
    </header>

    <!-- =========================================================
         SECTION 2: DOCUMENT TITLE
         ========================================================= -->
    <section class="title-row" data-section="document-title">
      <h1 id="quotation-title">
        Motor Insurance
        <span class="accent-word">Quotation</span>
      </h1>
    </section>

    <!-- =========================================================
         SECTION 3: COVERAGE SUMMARY + PAYMENT METHOD
         ========================================================= -->
    <section
      class="summary-grid"
      data-section="coverage-and-payment-summary"
      aria-label="Coverage details and payment method"
    >
      <article class="panel coverage-panel" data-section="coverage-information">
        <h2 class="panel-heading">
          Coverage &amp; Vehicle Information
          <span aria-hidden="true"> / </span>
          <span data-field="labels.coverage_secondary">保险与车辆资料</span>
        </h2>

        <div class="coverage-content">
          <table class="coverage-table">
            <caption class="visually-hidden">
              Motor insurance coverage and vehicle information
            </caption>

            <colgroup>
              <col />
              <col />
              <col />
            </colgroup>

            <tbody>
              <tr>
                <th scope="row">
                  Coverage Type
                  <span aria-hidden="true"> / </span>
                  <span data-field="labels.coverage_type_secondary">保险种类</span>
                </th>
                <td colspan="2" data-field="coverage.type">
                  Comprehensive / 综合
                </td>
              </tr>

              <tr>
                <th scope="row">
                  Car Model
                  <span aria-hidden="true"> / </span>
                  <span data-field="labels.car_model_secondary">车型</span>
                </th>
                <td colspan="2" data-field="vehicle.model">-</td>
              </tr>

              <tr>
                <th scope="row">NCD</th>
                <td colspan="2" data-field="coverage.ncd_percent">0.00%</td>
              </tr>

              <tr>
                <th scope="row">
                  Coverage Period
                  <span aria-hidden="true"> / </span>
                  <span data-field="labels.coverage_period_secondary">保险期限</span>
                </th>
                <td colspan="2" data-field="coverage.period">
                  01/01/1900–30/12/1900
                </td>
              </tr>

              <tr>
                <th scope="row">
                  Coverage Premium
                  <span aria-hidden="true"> / </span>
                  <span data-field="labels.coverage_premium_secondary">保费</span>
                </th>
                <td class="currency" data-field="currency.code">RM</td>
                <td class="amount" data-field="pricing.coverage_premium">-</td>
              </tr>

              <tr class="money-row">
                <th scope="row">Roadtax</th>
                <td class="currency" data-field="currency.code">RM</td>
                <td class="amount" data-field="pricing.roadtax">-</td>
              </tr>

              <tr class="money-row">
                <th scope="row">Runner Fee</th>
                <td class="currency" data-field="currency.code">RM</td>
                <td class="amount" data-field="pricing.runner_fee">20.00</td>
              </tr>

              <tr class="total-row">
                <th scope="row">
                  Total Premium
                  <span data-field="labels.total_premium_secondary">总额</span>
                </th>
                <td class="currency" data-field="currency.code">RM</td>
                <td class="amount" data-field="pricing.total_premium">20.00</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <aside class="payment-card" data-section="payment-method">
        <h2 class="payment-title">Payment Method</h2>

        <div class="bank-brand" aria-label="Bank">
          <span class="bank-mark" aria-hidden="true"></span>
          <span class="bank-name" data-field="payment.bank_name">
            HongLeong
          </span>
        </div>

        <p class="bank-details-label">Bank details</p>

        <p class="bank-account" data-field="payment.account_number">
          12303105859
        </p>

        <p class="payee-name" data-field="payment.account_name">
          RiskLocker Sdn. Bhd.
        </p>

        <p class="bank-branch" data-field="payment.bank_full_name">
          Hong Leong Bank
        </p>

        <div class="driver-row">
          <span class="driver-icon" aria-hidden="true"></span>
          <span data-field="coverage.driver_scope">All Driver</span>
        </div>
      </aside>
    </section>

    <!-- =========================================================
         SECTION 4: INCLUDED BENEFITS / OUR SPECIALS
         ========================================================= -->
    <section class="panel benefit-section" data-section="included-benefits">
      <h2 class="panel-heading">
        Our Specials
        <span aria-hidden="true"> / </span>
        <span data-field="labels.specials_secondary">特别优惠</span>
      </h2>

      <div class="benefit-grid" role="list">
        <article class="benefit-card" role="listitem" data-benefit-id="windscreen">
          <span class="benefit-icon" aria-hidden="true">WIN</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.windscreen.title">
              Windscreen Coverage (Up to RM )
            </h3>
            <p class="benefit-subtitle" data-field="benefits.windscreen.subtitle">
              汽车大镜保障（高达 RM）
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="allowance">
          <span class="benefit-icon" aria-hidden="true">CPA</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.allowance.title">
              Compassionate Allowance - RM 8,000
            </h3>
            <p class="benefit-subtitle" data-field="benefits.allowance.subtitle">
              关怀援助津贴 - RM 8,000
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="workmanship">
          <span class="benefit-icon" aria-hidden="true">3Y</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.workmanship.title">
              3 Years Workmanship Warranty
            </h3>
            <p class="benefit-subtitle" data-field="benefits.workmanship.subtitle">
              三年维修工艺保证
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="excess">
          <span class="benefit-icon" aria-hidden="true">EX</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.excess.title">
              Excess (RM)
            </h3>
            <p class="benefit-subtitle" data-field="benefits.excess.subtitle">
              自付额（RM）
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="unlimited-towing">
          <span class="benefit-icon" aria-hidden="true">TOW</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.unlimited_towing.title">
              Unlimited Towing
            </h3>
            <p class="benefit-subtitle" data-field="benefits.unlimited_towing.subtitle">
              无限拖车服务
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="ambulance">
          <span class="benefit-icon" aria-hidden="true">AMB</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.ambulance.title">
              Ambulance Fee (Up to RM 1,000)
            </h3>
            <p class="benefit-subtitle" data-field="benefits.ambulance.subtitle">
              救护车费用（高达 RM 1,000）
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="flood-relief">
          <span class="benefit-icon" aria-hidden="true">FLD</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.flood_relief.title">
              Flood Relief Allowance - RM 4,500
            </h3>
            <p class="benefit-subtitle" data-field="benefits.flood_relief.subtitle">
              水灾援助津贴 - RM 4,500
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="mobile-app">
          <span class="benefit-icon" aria-hidden="true">APP</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.mobile_app.title">
              One Touch Mobile App
            </h3>
            <p class="benefit-subtitle" data-field="benefits.mobile_app.subtitle">
              一触式手机应用程序
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="express-claim">
          <span class="benefit-icon" aria-hidden="true">CLM</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.express_claim.title">
              Express Claim (Below RM 10,000)
            </h3>
            <p class="benefit-subtitle" data-field="benefits.express_claim.subtitle">
              快速索赔（RM 10,000 以下）
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-benefit-id="border-towing">
          <span class="benefit-icon" aria-hidden="true">60K</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="benefits.border_towing.title">
              60km Towing from Malaysia Border (Plan 2)
            </h3>
            <p class="benefit-subtitle" data-field="benefits.border_towing.subtitle">
              马来西亚边境 60 公里拖车服务（计划 2）
            </p>
          </div>
        </article>
      </div>
    </section>

    <!-- =========================================================
         SECTION 5: OPTIONAL ADD-ONS
         ========================================================= -->
    <section class="panel benefit-section" data-section="optional-add-ons">
      <h2 class="panel-heading">
        You May Add On (With Additional Charges)
        <span aria-hidden="true"> / </span>
        <span data-field="labels.addons_secondary">可选附加保障（需额外付费）</span>
      </h2>

      <div class="benefit-grid" role="list">
        <article class="benefit-card" role="listitem" data-addon-id="betterment-waiver">
          <span class="benefit-icon" aria-hidden="true">WB</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="addons.betterment_waiver.title">
              Waiver of Betterment
            </h3>
            <p class="benefit-subtitle" data-field="addons.betterment_waiver.subtitle">
              免除折旧改善费
            </p>
          </div>
        </article>

        <article class="benefit-card" role="listitem" data-addon-id="passenger-liability">
          <span class="benefit-icon" aria-hidden="true">PL</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="addons.passenger_liability.title">
              Passenger Liability (LLP &amp; LLOP)
            </h3>
            <p class="benefit-subtitle" data-field="addons.passenger_liability.subtitle">
              乘客责任保障（LLP &amp; LLOP）
            </p>
          </div>
        </article>

        <article
          class="benefit-card with-brand"
          role="listitem"
          data-addon-id="e-hailing"
        >
          <span class="benefit-icon" aria-hidden="true">EH</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="addons.e_hailing.title">
              E-Hailing
            </h3>
            <p class="benefit-subtitle" data-field="addons.e_hailing.subtitle">
              电子召车
            </p>
          </div>
          <span class="partner-wordmark" data-field="addons.e_hailing.partner">
            Grab
          </span>
        </article>

        <article class="benefit-card" role="listitem" data-addon-id="special-perils">
          <span class="benefit-icon" aria-hidden="true">SP</span>
          <div class="benefit-copy">
            <h3 class="benefit-title" data-field="addons.special_perils.title">
              Inclusion of Special Perils
            </h3>
            <p class="benefit-subtitle" data-field="addons.special_perils.subtitle">
              包含特殊灾害保障
            </p>
          </div>
        </article>
      </div>
    </section>

    <!-- =========================================================
         SECTION 6: FOOTER
         ========================================================= -->
    <footer class="document-footer" data-section="document-footer">
      <span data-field="footer.terms_note">*Terms &amp; Conditions Apply</span>
      <span class="footer-separator" aria-hidden="true">|</span>
      <strong>Validity:</strong>
      <span data-field="quotation.valid_until">02/08/2026</span>
    </footer>

    <!--
      MACHINE-READABLE DOCUMENT MAP

      This JSON is intentionally embedded for non-vision AI agents and code
      generators. It describes the visual order and meaning of the document.
      Browsers do not display it.
    -->
    <script type="application/json" id="quotation-document-map">
      {
        "documentType": "motor-insurance-quotation",
        "page": {
          "size": "A4",
          "orientation": "portrait",
          "visualOrder": [
            "document-header",
            "document-title",
            "coverage-and-payment-summary",
            "included-benefits",
            "optional-add-ons",
            "document-footer"
          ]
        },
        "layout": {
          "document-header": {
            "type": "three-column",
            "columns": [
              "agency-brand",
              "insurer-brand",
              "quotation-reference"
            ]
          },
          "coverage-and-payment-summary": {
            "type": "two-column",
            "left": "coverage-information",
            "right": "payment-method"
          },
          "included-benefits": {
            "type": "two-column-card-grid",
            "cardCount": 10
          },
          "optional-add-ons": {
            "type": "two-column-card-grid",
            "cardCount": 4
          }
        },
        "dynamicFieldConvention": {
          "selector": "[data-field]",
          "example": {
            "selector": "[data-field='pricing.total_premium']",
            "meaning": "Final premium amount without the currency code"
          }
        }
      }
    </script>
  </main>
</body>
</html>s