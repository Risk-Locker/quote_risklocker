"use client";

import React from "react";

const BLK = "#1D1D1B";
const RED = "#E52320";

export function FreeCoverageGiftSvg({ width = 28, height = 24 }: { width?: number; height?: number }) {
  return (
    <svg width={width} height={height} viewBox="0 0 36 30" fill="none" aria-hidden="true">
      <path
        d="M13.5 8.5C10 8.5 8.2 6.8 8.2 5C8.2 3.3 9.7 2.2 11.4 2.2C13.6 2.2 15.1 5.2 15.6 8.5H13.5Z"
        stroke="#FFFFFF"
        strokeWidth="2.1"
        strokeLinejoin="round"
      />
      <path
        d="M17.7 8.5C21.2 8.5 23 6.8 23 5C23 3.3 21.5 2.2 19.8 2.2C17.6 2.2 16.1 5.2 15.6 8.5H17.7Z"
        stroke="#FFFFFF"
        strokeWidth="2.1"
        strokeLinejoin="round"
      />
      <rect x="4" y="9" width="10.4" height="5" rx="1.2" fill="#FFFFFF" />
      <rect x="16.8" y="9" width="10.4" height="5" rx="1.2" fill="#FFFFFF" />
      <rect x="5.4" y="15.8" width="9" height="10.8" rx="1.2" fill="#FFFFFF" />
      <rect x="16.8" y="15.8" width="9" height="10.8" rx="1.2" fill="#FFFFFF" />
      <circle cx="25.5" cy="18.2" r="8.2" fill="#5ABA00" stroke="#E52320" strokeWidth="1.4" />
      <path
        d="M21.8 18.2L24.4 20.8L29.4 15.6"
        stroke="#FFFFFF"
        strokeWidth="2.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const ALIAS_MAP: Record<string, string> = {
  passengers: "llop",
  crane: "boom_damage",
  all_driver: "all_drivers",
  "own-damage": "own_damage",
  "third-party-bi": "third_party_bi",
  "third-party-bodily-injury": "third_party_bi",
  "third-party-property": "third_party_property",
  "third-party-property-damage": "third_party_property",
  "legal-costs-defense": "legal_defense",
  "legal-defense": "legal_defense",
  "repair-workmanship-warranty": "repair_workmanship_warranty",
  "agreed-value-market-value": "agreed_value",
  "cashback-no-claim": "cashback_no_claim",
  "increased-tppd": "increased_tppd",
  "first-loss-flood": "first_loss_flood",
  "car-detailing-cleanup": "car_detailing_cleanup",
  "out-of-pocket-allowance": "out_of_pocket_allowance",
  "cross-border": "cross_border",
  "ferry-transit": "ferry_transit",
  "child-car-seat": "child_car_seat",
  "payd-telematics": "payd_telematics",
  "natural-falling-objects": "natural_falling_objects",
  "side-mirror-protection": "side_mirror_protection",
  "document-replacement": "document_replacement",
  "total-loss-theft-allowance": "total_loss_theft_allowance",
  "flood-relief-allowance": "flood_relief_allowance",
  "personal-belongings-theft": "personal_belongings_theft",
  "legal-liability-to-pillion": "pillion",
  "daily-hospital-income": "daily_hospital_income",
  "double-indemnity": "double_indemnity",
  "medical-expenses": "medical_expenses",
  "permanent-disablement": "permanent_disablement",
  "accidental-death": "pa",
  "ev-charging-bodily-injury": "ev_charging_bodily_injury",
  "ev-home-content-fire": "ev_home_content_fire",
  "ev-battery-depletion-towing": "ev_towing",
  "ev-home-charger-liability": "ev_liability",
  "ev-wall-charger": "ev_charger",
  "lonpac-ev-smart-pack": "lonpac_ev_smart_pack",
  "attached-trailers": "attached_trailers",
  "cargo-protection": "cargo_protection",
  "commercial-driver-crew-pa": "commercial_driver_crew_pa",
  "authorized-attendants": "non_fare_passenger",
  "tool-of-trade": "third_party_working",
  "private-car-365": "private_car_365",
  "smart-driver-pa": "smart_driver_pa",
  "motor-pa-plus": "motor_pa_plus",
  "oto-360": "oto_360",
  "driver-passenger-protector": "driver_passenger_protector",
  "motorshield-bundle": "motorshield_bundle",
  "sompo-motor-nhancer": "sompo_motor_nhancer",
  "auto-buddy-malaysia": "auto_buddy_malaysia",
  "motor-easy": "motor_easy",
  "betterment-protection": "betterment",
  "all-drivers": "all_drivers",
  "special-perils": "special_perils",
  "strike-riot-civil-commotion": "srcc",
  "repaint-spray-paint": "respray",
  "gas-conversion-kit": "gas_conversion",
  "repair-allowance": "cart",
  "vehicle-accessories": "accessories",
  "ncd-relief": "ncd",
  "key-replacement": "key_care",
  "legal-liability-of-passengers": "llop",
  "legal-liability-to-passengers": "llp",
  "e-hailing-extension": "ehailing",
  "boom-damage": "boom_damage",
};

export function Design2BenefitIconSvg({ hint, size = 38 }: { hint?: string; size?: number }) {
  const raw = (hint || "generic").trim().toLowerCase();
  const key = ALIAS_MAP[raw] || raw;

  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      {(() => {
        switch (key) {
          case "windscreen":
            return (
              <>
                <polygon points="10,13 38,13 43,35 5,35" fill="#FFFFFF" stroke={BLK} strokeWidth="2.7" strokeLinejoin="round" />
                <path d="M26 34L29.5 27L26.5 24.5L32 18.5" stroke={RED} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M29.5 27L34.5 28.5M28 22.5L23.5 21.5" stroke={RED} strokeWidth="1.8" strokeLinecap="round" />
              </>
            );
          case "towing":
            return (
              <>
                <path d="M6 27H30V31H6Z" fill={BLK} />
                <path d="M30 19H36.8L41.5 24.5V31H30V19Z" fill={BLK} />
                <path d="M32 21H36L39 24.5H32V21Z" fill="#FFFFFF" />
                <path d="M8.5 26C9 21.8 11.4 19 15 19H21C24.2 19 26.2 21.5 27.5 23.5C28.8 24 29 25 29 26H8.5Z" fill={RED} />
                <path d="M12.5 20.6H19.5L22.2 23.2H11.2L12.5 20.6Z" fill="#FFFFFF" />
                <circle cx="13.5" cy="31.8" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <circle cx="35.5" cy="31.8" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <circle cx="13.5" cy="31.8" r="1.2" fill={BLK} />
                <circle cx="35.5" cy="31.8" r="1.2" fill={BLK} />
              </>
            );
          case "unlimited_towing":
            return (
              <>
                <path
                  d="M17.2 10C14.2 10 12 12 12 14.6C12 17.2 14.2 19.2 17.2 19.2C20.2 19.2 22.3 16.4 24 14.6C25.7 12.8 27.8 10 30.8 10C33.8 10 36 12 36 14.6C36 17.2 33.8 19.2 30.8 19.2C27.8 19.2 25.7 16.4 24 14.6C22.3 12.8 20.2 10 17.2 10Z"
                  fill="none"
                  stroke={RED}
                  strokeWidth="2.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path d="M8 31H24V34.5H8Z" fill={BLK} />
                <path d="M24 23.5H33.5L39 28.5V34.5H24V23.5Z" fill={BLK} />
                <path d="M26.5 25.6H32.2L35.8 28.8H26.5V25.6Z" fill="#FFFFFF" />
                <path d="M24 26L14 21.5L11.5 24.5" fill="none" stroke={BLK} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M11.5 24.5V27.6C11.5 28.8 10.4 29.5 9.2 29.2" fill="none" stroke={RED} strokeWidth="2.2" strokeLinecap="round" />
                <circle cx="14.5" cy="35.2" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <circle cx="33.5" cy="35.2" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <circle cx="14.5" cy="35.2" r="1.2" fill={BLK} />
                <circle cx="33.5" cy="35.2" r="1.2" fill={BLK} />
                <line x1="6" y1="39.5" x2="42" y2="39.5" stroke={BLK} strokeWidth="1.8" strokeLinecap="round" />
              </>
            );
          case "llop":
            return (
              <>
                <path d="M5 24L8.5 17H21.5L24.5 24V31H5V24Z" fill={BLK} />
                <rect x="7" y="30" width="3.5" height="3.5" rx="0.8" fill={BLK} />
                <rect x="19" y="30" width="3.5" height="3.5" rx="0.8" fill={BLK} />
                <path d="M9.8 19H20.2L22 23H8L9.8 19Z" fill="#FFFFFF" />
                <circle cx="9.2" cy="26.5" r="1.6" fill="#FFFFFF" />
                <circle cx="20.2" cy="26.5" r="1.6" fill="#FFFFFF" />
                <path d="M19 26L23 18.5H38.5L42.5 26V34H19V26Z" fill={BLK} stroke="#FFFFFF" strokeWidth="1.3" />
                <rect x="21.5" y="33" width="3.8" height="3.5" rx="0.8" fill={BLK} />
                <rect x="36.2" y="33" width="3.8" height="3.5" rx="0.8" fill={BLK} />
                <path d="M24.4 20.6H37L39 24.8H22.4L24.4 20.6Z" fill="#FFFFFF" />
                <circle cx="23.8" cy="29" r="1.8" fill="#FFFFFF" />
                <circle cx="37.6" cy="29" r="1.8" fill="#FFFFFF" />
                <path d="M23 16.5L20 11L24.5 13.5L27 8.5L29.5 13.5L34 11L31 16.5" fill="none" stroke={RED} strokeWidth="2.1" strokeLinejoin="round" strokeLinecap="round" />
              </>
            );
          case "llp":
            return (
              <>
                <path d="M17 28C18.5 23.2 21.8 20.5 27.5 20.5H36.5C40.5 20.5 43.2 23.2 44 26.5V32H17V28Z" fill={BLK} />
                <path d="M22.5 22.4H34.5L38 25.8H20.5L22.5 22.4Z" fill="#FFFFFF" />
                <circle cx="23.5" cy="32.5" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <circle cx="38.5" cy="32.5" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <circle cx="10.2" cy="14.5" r="2.6" fill={RED} />
                <path d="M10.5 17.8L13.5 23.5L8.2 27L6.5 34.5M12.2 24.5L15.8 31.8M9.8 19.5L4.8 22.5M12.5 20L17.2 19" stroke={RED} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M16.5 16L14 12.5M18.8 18.5L18.8 14.5" stroke={RED} strokeWidth="1.8" strokeLinecap="round" />
              </>
            );
          case "special_perils":
            return (
              <>
                <path d="M11 29C12 24.5 15 22.5 19.5 22.5H29C33.5 22.5 36.2 24.8 37.2 29" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <path d="M6 31.5Q10.5 28.5 15 31.5T24 31.5T33 31.5T42 31.5" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <path d="M8 36.5Q12 34 16 36.5T24 36.5T32 36.5T40 36.5" fill="none" stroke={BLK} strokeWidth="2.1" strokeLinecap="round" />
                <path d="M24 8L32.5 11.2V17.8C32.5 22.8 28.8 26.2 24 28C19.2 26.2 15.5 22.8 15.5 17.8V11.2L24 8Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" strokeLinejoin="round" />
                <path d="M20.2 17.8L23 20.6L28.4 15.2" stroke={RED} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "betterment":
            return (
              <>
                <path d="M11 19A14 14 0 0 1 35.5 14.5" fill="none" stroke={BLK} strokeWidth="2.5" strokeLinecap="round" />
                <polyline points="32.2,10.5 36.2,15.2 30.8,16.5" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M37 29A14 14 0 0 1 12.5 33.5" fill="none" stroke={BLK} strokeWidth="2.5" strokeLinecap="round" />
                <polyline points="15.8,37.5 11.8,32.8 17.2,31.5" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M24 15.8L26.2 18.2L29.6 17.6L30.2 20.8L33 22.6L31.4 25.5L32.4 28.8L29.2 29.8L27.4 32.6L24 31.6L20.6 32.6L18.8 29.8L15.6 28.8L16.6 25.5L15 22.6L17.8 20.8L18.4 17.6L21.8 18.2Z" fill={RED} />
                <circle cx="24" cy="24.2" r="3.4" fill="#FFFFFF" />
              </>
            );
          case "all_drivers":
            return (
              <>
                <circle cx="26" cy="14" r="4.5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <circle cx="15.5" cy="20.5" r="4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <path d="M8.5 34.5C8.5 29.5 11.5 26.8 15.5 26.8C19.5 26.8 22.5 29.5 22.5 34.5" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <path d="M21 21.5C22.5 20.6 24.2 20.2 26 20.2C28 20.2 29.8 20.7 31.2 21.8" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <path d="M33.5 22.5L40 24.8V30.5C40 34.8 37.2 37.6 33.5 39C29.8 37.6 27 34.8 27 30.5V24.8L33.5 22.5Z" fill="#FFFFFF" stroke={RED} strokeWidth="2.2" strokeLinejoin="round" />
                <path d="M33.5 22.5L40 24.8V30.5C40 34.8 37.2 37.6 33.5 39V22.5Z" fill={RED} />
              </>
            );
          case "srcc":
            return (
              <>
                <path d="M19 20.5C20.5 16 22.5 12.2 25.5 9.5C25.2 13 27.2 14.5 28.5 12.5C29.8 15.5 32 13.5 32.8 10.5C35.2 14 36.2 17.8 34.8 21.5" fill="none" stroke={RED} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M9.5 25.5L13.5 19.5H27.5L32.5 25.5H37.5C39.2 25.5 40.5 26.8 40.5 28.5V33.5H7.5V27.5C7.5 26.4 8.4 25.5 9.5 25.5Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <circle cx="14.5" cy="34.5" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
                <circle cx="33.5" cy="34.5" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
              </>
            );
          case "respray":
            return (
              <>
                <rect x="14.5" y="10.5" width="7.5" height="9" rx="1" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <path d="M18.2 19.5V23.2M13 10.5H23.5" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <path d="M8.5 23.2H27.5V27.2H21L14.5 38.2H9.5L15 27.2H8.5V23.2Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" strokeLinejoin="round" />
                <path d="M22.5 27.2L20.2 32.5" stroke={BLK} strokeWidth="2" strokeLinecap="round" />
                <circle cx="31.5" cy="24.5" r="1.2" fill={RED} />
                <circle cx="35.5" cy="22.2" r="1.4" fill={RED} />
                <circle cx="36" cy="25.2" r="1.3" fill={RED} />
                <circle cx="35.5" cy="28.2" r="1.4" fill={RED} />
                <circle cx="40" cy="20.2" r="1.3" fill={RED} />
                <circle cx="40.5" cy="24.8" r="1.5" fill={RED} />
                <circle cx="40" cy="29.5" r="1.3" fill={RED} />
              </>
            );
          case "gas_conversion":
            return (
              <>
                <rect x="18.5" y="9" width="11" height="4.5" rx="1" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <rect x="13" y="13.5" width="22" height="25.5" rx="6" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <path d="M24 19.5C26.5 22.8 29.2 25.5 29.2 28.8C29.2 31.8 26.8 34 24 34C21.2 34 18.8 31.8 18.8 28.8C18.8 26.2 20.5 24 22 22.5C22 24 23 24.8 24 24.8C24 22.8 24 21 24 19.5Z" fill={RED} />
                <path d="M24 27.2C25 28.5 25.5 29.5 25.5 30.5A1.5 1.5 0 0 1 22.5 30.5C22.5 29.5 23.2 28.2 24 27.2Z" fill="#FFFFFF" />
              </>
            );
          case "cart":
            return (
              <>
                <rect x="9" y="12.5" width="24" height="22" rx="2.5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
                <line x1="9" y1="19" x2="33" y2="19" stroke={BLK} strokeWidth="2.2" />
                <line x1="15.5" y1="9" x2="15.5" y2="14.5" stroke={BLK} strokeWidth="2.5" strokeLinecap="round" />
                <line x1="26.5" y1="9" x2="26.5" y2="14.5" stroke={BLK} strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="14.5" cy="24" r="1.4" fill={BLK} />
                <circle cx="20" cy="24" r="1.4" fill={BLK} />
                <circle cx="14.5" cy="29" r="1.4" fill={BLK} />
                <circle cx="20" cy="29" r="1.4" fill={BLK} />
                <circle cx="32.5" cy="31.5" r="8.2" fill={RED} />
                <text x="32.5" y="35.3" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="11.5" fontWeight="900" fill="#FFFFFF">$</text>
              </>
            );
          case "accessories":
            return (
              <>
                <circle cx="24" cy="24" r="14.5" fill="#FFFFFF" stroke={BLK} strokeWidth="3.4" />
                <circle cx="24" cy="24" r="10.2" fill="none" stroke={BLK} strokeWidth="1.8" />
                <circle cx="24" cy="24" r="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <path d="M24 14L26.5 19.5H21.5Z" fill={RED} />
                <path d="M33.5 21L28.5 24.5L26.8 19.8Z" fill={RED} />
                <path d="M29.8 32.2L24.5 28.8L28.6 26Z" fill={RED} />
                <path d="M18.2 32.2L19.4 26L23.5 28.8Z" fill={RED} />
                <path d="M14.5 21L21.2 19.8L19.5 24.5Z" fill={RED} />
              </>
            );
          case "ncd":
            return (
              <>
                <path d="M24 9L37.5 13.5V23.8C37.5 32 31.6 37.6 24 40C16.4 37.6 10.5 32 10.5 23.8V13.5L24 9Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.6" strokeLinejoin="round" />
                <text x="24" y="27.2" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="10.5" fontWeight="900" letterSpacing="0.4" fill={RED}>NCD</text>
              </>
            );
          case "pa":
            return (
              <>
                <path d="M29 14L33 27.5" stroke={BLK} strokeWidth="3" strokeLinecap="round" />
                <circle cx="21" cy="14" r="4.2" fill={BLK} />
                <path d="M14 23C14 20.5 16.5 19.5 21 19.5C25.5 19.5 27.8 20.8 27.8 23.5V31.5H14V23Z" fill={BLK} />
                <rect x="15" y="32" width="5" height="6.8" rx="1" fill={BLK} />
                <rect x="21.8" y="32" width="5" height="6.8" rx="1" fill={BLK} />
                <path d="M13.5 24L25 27.5L23.5 32.2L13.5 29Z" fill={RED} />
                <line x1="19.5" y1="19.5" x2="23.5" y2="27" stroke={RED} strokeWidth="2" strokeLinecap="round" />
              </>
            );
          case "key_care":
            return (
              <>
                <g transform="rotate(-42 21 27)">
                  <rect x="11" y="19" width="22" height="14" rx="5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                  <circle cx="17" cy="26" r="2.2" fill="none" stroke={BLK} strokeWidth="2" />
                  <circle cx="25.5" cy="23.5" r="1.4" fill={RED} />
                  <circle cx="25.5" cy="28.5" r="1.4" fill={BLK} />
                  <line x1="28.5" y1="26" x2="30.5" y2="26" stroke={BLK} strokeWidth="2" strokeLinecap="round" />
                </g>
                <path d="M27.5 12.5A7.5 7.5 0 0 1 35 20" fill="none" stroke={RED} strokeWidth="2.2" strokeLinecap="round" />
                <path d="M30.5 8.5A12 12 0 0 1 39.5 18" fill="none" stroke={RED} strokeWidth="2.2" strokeLinecap="round" />
              </>
            );
          case "international_towing":
            return (
              <>
                <circle cx="14.5" cy="14" r="4.2" fill={BLK} />
                <rect x="10.8" y="13.2" width="7.4" height="1.6" fill="#FFFFFF" />
                <circle cx="24" cy="13.5" r="4.2" fill={RED} />
                <rect x="20.2" y="13.8" width="7.6" height="3.6" fill="#FFFFFF" />
                <circle cx="33.5" cy="14" r="4.2" fill="#FFFFFF" stroke={BLK} strokeWidth="1.3" />
                <rect x="29.6" y="13" width="7.8" height="2" fill={RED} />
                <path d="M6 29H30V33H6Z" fill={BLK} />
                <path d="M30 22H36.8L41.5 27V33H30V22Z" fill={BLK} />
                <path d="M32 23.8H36L38.8 27H32V23.8Z" fill="#FFFFFF" />
                <path d="M8.5 28C9 24.4 11.4 22 14.8 22H20.8C23.8 22 25.8 24.2 27 26C28.2 26.5 28.5 27.3 28.5 28H8.5Z" fill={RED} />
                <circle cx="13.5" cy="34.2" r="3.2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <circle cx="35.5" cy="34.2" r="3.2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
              </>
            );
          case "ev_charger":
            return (
              <>
                <rect x="10" y="10" width="18" height="24" rx="3.2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <path d="M20.5 15.5L15.5 22.8H19.8L18.2 28.8L23.5 21.2H19.2L20.5 15.5Z" fill={RED} />
                <path d="M19 34V37.2C19 39.2 20.8 40.5 23 40.5H31.5C33.8 40.5 35.5 39 35.5 36.8V26.5" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <rect x="33" y="21" width="5" height="5.5" rx="1" fill={BLK} />
                <line x1="34.4" y1="18.2" x2="34.4" y2="21" stroke={BLK} strokeWidth="2" strokeLinecap="round" />
                <line x1="36.6" y1="18.2" x2="36.6" y2="21" stroke={BLK} strokeWidth="2" strokeLinecap="round" />
              </>
            );
          case "ev_towing":
            return (
              <>
                <rect x="27" y="18.5" width="4" height="3.2" rx="1" fill={RED} />
                <path d="M24 17.5L21.5 15.5M29 16V13M34 17.5L36.5 15.5" stroke={RED} strokeWidth="1.9" strokeLinecap="round" />
                <path d="M26 22H35.5L40 27.5V34H26V22Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" strokeLinejoin="round" />
                <path d="M28.2 24H34.2L37.4 27.5H28.2V24Z" fill={BLK} />
                <line x1="16" y1="29" x2="26" y2="29" stroke={BLK} strokeWidth="2.5" />
                <line x1="19" y1="22.5" x2="26" y2="27" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <g transform="rotate(14 14 28)">
                  <path d="M5.5 27.5L8.2 22.5H17.5L21.2 27.5V31.5H5.5V27.5Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.1" strokeLinejoin="round" />
                  <circle cx="10.2" cy="32.2" r="2.6" fill="#FFFFFF" stroke={BLK} strokeWidth="2" />
                </g>
                <circle cx="29.5" cy="34.5" r="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <circle cx="37.2" cy="34.5" r="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
              </>
            );
          case "ev_liability":
            return (
              <>
                <path d="M12.5 34.5A14 14 0 1 1 35 33.5" fill="none" stroke={BLK} strokeWidth="2.6" strokeLinecap="round" />
                <path d="M11 33.5L17.5 24.5L23 28.5L16.5 37.5Z" fill={BLK} />
                <line x1="20.5" y1="22.8" x2="23" y2="19.5" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <line x1="24" y1="25.5" x2="26.5" y2="22.2" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <path d="M29.8 25L25.2 31.2H28.8L27.5 36.5L32.8 29.8H29.2L29.8 25Z" fill={RED} />
              </>
            );
          case "ehailing":
            return (
              <>
                <line x1="7" y1="18.5" x2="12" y2="18.5" stroke={BLK} strokeWidth="2" strokeLinecap="round" />
                <line x1="5.5" y1="22" x2="11" y2="22" stroke={BLK} strokeWidth="2" strokeLinecap="round" />
                <rect x="13" y="18.5" width="8.5" height="7" rx="1.2" fill={RED} />
                <circle cx="27.5" cy="13.5" r="3.4" fill={BLK} />
                <path d="M25.5 18L29.5 21.5L34.5 22M26.5 18.5L24.5 25.5L29 29.5" stroke={BLK} strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M14 29H35.5L33 21.5" fill="none" stroke={BLK} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="17" cy="33" r="4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <circle cx="35.5" cy="33" r="4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
              </>
            );
          case "non_fare_passenger":
            return (
              <>
                <circle cx="24" cy="14" r="4.2" fill={BLK} />
                <path d="M16.5 23.5C16.5 20.5 19.5 19.2 24 19.2C28.5 19.2 31.5 20.5 31.5 23.5V32.5H16.5V23.5Z" fill={BLK} />
                <path d="M18 32.5V39M30 32.5V39" stroke={BLK} strokeWidth="3.6" strokeLinecap="round" />
                <line x1="16.5" y1="30.5" x2="31" y2="20" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
                <path d="M14 23.5L9.5 20.5L13 26.5L8.5 29L13.5 30.5L11.5 34.5" fill="none" stroke={RED} strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "third_party_working":
            return (
              <>
                <path d="M13 17C13 13 16 10.5 20 10.5C24 10.5 27 13 27 17Z" fill={BLK} />
                <line x1="11.2" y1="17.2" x2="28.8" y2="17.2" stroke={BLK} strokeWidth="2.4" strokeLinecap="round" />
                <path d="M14.5 18V21.8C14.5 24.5 17 26.5 20 26.5C23 26.5 25.5 24.5 25.5 21.8V18" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <path d="M10.5 37V32.5C10.5 29.8 14 28.5 20 28.5C24 28.5 26 29.2 27.5 30.2V37H10.5Z" fill={BLK} />
                <polygon points="34.5,24 42.5,37.5 26.5,37.5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" strokeLinejoin="round" />
                <line x1="34.5" y1="29.5" x2="34.5" y2="33.2" stroke={RED} strokeWidth="2.1" strokeLinecap="round" />
                <circle cx="34.5" cy="35.3" r="1.1" fill={RED} />
              </>
            );
          case "boom_damage":
            return (
              <>
                <line x1="24" y1="12" x2="24" y2="16.5" stroke={BLK} strokeWidth="2.2" />
                <rect x="19" y="16.5" width="10" height="5.5" rx="0.8" fill={BLK} />
                <circle cx="24" cy="26.5" r="2.2" fill={BLK} />
                <path d="M24 29.2V35.5M20.5 31.5H27.5M21.8 39L24 34.5L26.2 39" stroke={BLK} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="24" cy="24" r="14.5" fill="none" stroke={RED} strokeWidth="2.8" />
                <line x1="13.8" y1="13.8" x2="34.2" y2="34.2" stroke={RED} strokeWidth="2.8" strokeLinecap="round" />
              </>
            );
          case "overturning":
            return (
              <>
                <path d="M21 15.5C21.8 12.8 23.2 11.2 24.5 10C24.4 12.5 25.8 13.2 27 11.2C28 13.5 29.8 12.2 30.2 10.5C31.5 12.8 32 14.8 31 17" fill="none" stroke={RED} strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
                <g transform="rotate(14 23 26)">
                  <path d="M8.5 22.5H39.5V27.5L35 33.5H15.5L9.5 28V22.5Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" strokeLinejoin="round" />
                  <circle cx="14.5" cy="21.5" r="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                  <circle cx="33.5" cy="21.5" r="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                </g>
                <line x1="7" y1="36.5" x2="41" y2="36.5" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
              </>
            );
          case "own_damage":
            return (
              <>
                <path d="M8 27L12.5 19.5H27L31.5 25.5H37.5C39.2 25.5 40.5 26.8 40.5 28.5V33H7.5V28.2C7.5 27.6 7.7 27.2 8 27Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <path d="M14 21.2H25.5L29 25.5H12.2L14 21.2Z" fill={BLK} />
                <circle cx="14.5" cy="33.5" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <circle cx="33" cy="33.5" r="3.4" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" />
                <path d="M35.5 14.5L38 11.5M38.5 18L42.5 17M37 21.5L41.5 22.5" stroke={RED} strokeWidth="2.3" strokeLinecap="round" />
                <circle cx="34.5" cy="18.2" r="2.2" fill={RED} />
              </>
            );
          case "third_party_bi":
            return (
              <>
                <path d="M22 9L34 13V23C34 30.5 28.8 36 22 38.5C15.2 36 10 30.5 10 23V13L22 9Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <circle cx="22" cy="18.5" r="3.3" fill={BLK} />
                <path d="M15.8 29C15.8 25.5 18.5 24 22 24C25.5 24 28.2 25.5 28.2 29" fill="none" stroke={BLK} strokeWidth="2.4" strokeLinecap="round" />
                <circle cx="35.5" cy="32.5" r="7.5" fill={RED} stroke="#FFFFFF" strokeWidth="1.5" />
                <path d="M35.5 28.8V36.2M31.8 32.5H39.2" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
              </>
            );
          case "third_party_property":
            return (
              <>
                <path d="M26 20L34 13.5L42 20V35H26V20Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" strokeLinejoin="round" />
                <rect x="31.5" y="25.5" width="5" height="9.5" fill={BLK} />
                <path d="M6 27L9.5 21.5H19L22.5 27V33.5H6V27Z" fill={BLK} />
                <circle cx="10.5" cy="34" r="2.6" fill="#FFFFFF" stroke={BLK} strokeWidth="2" />
                <circle cx="19" cy="34" r="2.6" fill="#FFFFFF" stroke={BLK} strokeWidth="2" />
                <path d="M22 18L24.5 14.5L26.5 18.5L30 16.5" fill="none" stroke={RED} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "legal_defense":
            return (
              <>
                <g transform="rotate(-35 22 20)">
                  <rect x="13" y="13" width="16" height="8" rx="1.5" fill={BLK} />
                  <line x1="21" y1="21" x2="21" y2="35" stroke={BLK} strokeWidth="3.2" strokeLinecap="round" />
                </g>
                <rect x="10" y="34" width="22" height="4.5" rx="1.5" fill={RED} />
                <line x1="7" y1="38.5" x2="35" y2="38.5" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
              </>
            );
          case "repair_workmanship_warranty":
            return (
              <>
                <circle cx="23" cy="23" r="13.5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <path d="M18.5 17.5A4.2 4.2 0 0 0 24 22.8L28.5 27.3A1.6 1.6 0 0 1 26.2 29.6L21.7 25.1A4.2 4.2 0 0 0 16.4 19.6L19 22.2L21.1 20.1L18.5 17.5Z" fill={BLK} />
                <circle cx="34.5" cy="34" r="7.5" fill={RED} stroke="#FFFFFF" strokeWidth="1.5" />
                <path d="M31.2 34L33.5 36.3L38 31.8" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "agreed_value":
            return (
              <>
                <path d="M10 13H25L36 24L24 36L13 25V13Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <circle cx="17" cy="19" r="2.2" fill={BLK} />
                <circle cx="33.5" cy="31.5" r="7.5" fill={RED} stroke="#FFFFFF" strokeWidth="1.5" />
                <path d="M30 31.5L32.5 34L37.2 29" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "cashback_no_claim":
            return (
              <>
                <path d="M11 21A13.5 13.5 0 0 1 36 16.5" fill="none" stroke={BLK} strokeWidth="2.5" strokeLinecap="round" />
                <polyline points="32.5,11.5 36.5,17 31,18" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M37 27A13.5 13.5 0 0 1 12 31.5" fill="none" stroke={BLK} strokeWidth="2.5" strokeLinecap="round" />
                <polyline points="15.5,36.5 11.5,31 17,30" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="24" cy="24" r="6.8" fill={RED} />
                <text x="24" y="27.5" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="9.5" fontWeight="900" fill="#FFFFFF">%</text>
              </>
            );
          case "increased_tppd":
            return (
              <>
                <path d="M24 9L37 13.5V23.8C37 31.8 31.4 37.4 24 39.8C16.6 37.4 11 31.8 11 23.8V13.5L24 9Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" strokeLinejoin="round" />
                <path d="M24 31V17.5M18.5 22.5L24 17L29.5 22.5" stroke={RED} strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
                <line x1="18.5" y1="33.5" x2="29.5" y2="33.5" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
              </>
            );
          case "first_loss_flood":
            return (
              <>
                <path d="M10 23A14 14 0 0 1 38 23Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <path d="M24 9V31C24 33 22.5 34.5 20.8 34.5" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <path d="M8 38Q12.5 35.2 17 38T26 38T35 38T41 38" fill="none" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <rect x="17" y="15.5" width="14" height="3.2" rx="1.4" fill={RED} />
              </>
            );
          case "car_detailing_cleanup":
            return (
              <>
                <path d="M10 27L14.5 19.5H29L33.5 26H38.5C40 26 41 27 41 28.5V33.5H7.5V28.5C7.5 27.6 8.6 27 10 27Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <circle cx="14.5" cy="34" r="3.2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <circle cx="33.5" cy="34" r="3.2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.2" />
                <path d="M18 9L19.4 13L23.5 14.4L19.4 15.8L18 19.8L16.6 15.8L12.5 14.4L16.6 13Z" fill={RED} />
                <path d="M33 10L34 12.6L36.6 13.6L34 14.6L33 17.2L32 14.6L29.4 13.6L32 12.6Z" fill={RED} />
              </>
            );
          case "out_of_pocket_allowance":
            return (
              <>
                <rect x="8" y="15" width="28" height="21" rx="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <path d="M11 15L29 10L32 15" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinejoin="round" />
                <rect x="27" y="22.5" width="11" height="6.5" rx="1.8" fill={BLK} />
                <circle cx="30.5" cy="25.8" r="1.4" fill="#FFFFFF" />
                <circle cx="18" cy="25.5" r="5.5" fill={RED} />
                <text x="18" y="28.6" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="8.5" fontWeight="900" fill="#FFFFFF">$</text>
              </>
            );
          case "cross_border":
            return (
              <>
                <circle cx="21.5" cy="25" r="13" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
                <ellipse cx="21.5" cy="25" rx="6" ry="13" fill="none" stroke={BLK} strokeWidth="1.8" />
                <line x1="9" y1="25" x2="34" y2="25" stroke={BLK} strokeWidth="1.8" />
                <path d="M34 9.5C30.4 9.5 27.5 12.3 27.5 15.8C27.5 20.5 34 26.5 34 26.5C34 26.5 40.5 20.5 40.5 15.8C40.5 12.3 37.6 9.5 34 9.5Z" fill={RED} stroke="#FFFFFF" strokeWidth="1.3" />
                <circle cx="34" cy="15.6" r="2.2" fill="#FFFFFF" />
              </>
            );
          case "ferry_transit":
            return (
              <>
                <path d="M16 18.5L18.5 14H28.5L31 18.5H16Z" fill={RED} />
                <path d="M13 21H34L36.5 24.5H11L13 21Z" fill={BLK} />
                <path d="M7.5 24.5H40.5L36.5 32.5H11.5L7.5 24.5Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <path d="M6 37Q10.5 34.2 15 37T24 37T33 37T42 37" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
              </>
            );
          case "child_car_seat":
            return (
              <>
                <path d="M16 11C16 9.5 17.5 8.5 19.5 8.5H23C25.5 8.5 27 10.5 27 13V24.5H34.5C36.5 24.5 38 26 38 28V31.5C38 33.5 36.5 35 34.5 35H16C13.5 35 12 33 12 30.5V15C12 12.8 13.8 11 16 11Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" strokeLinejoin="round" />
                <path d="M19.5 13V26.5M23.5 13V26.5" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <circle cx="21.5" cy="26.5" r="3.8" fill={RED} />
                <line x1="15" y1="38.5" x2="35" y2="38.5" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
              </>
            );
          case "payd_telematics":
            return (
              <>
                <path d="M9 32A15.5 15.5 0 1 1 39 32" fill="#FFFFFF" stroke={BLK} strokeWidth="2.6" strokeLinecap="round" />
                <line x1="12" y1="32" x2="36" y2="32" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <path d="M24 29L15.5 20.5" stroke={RED} strokeWidth="2.8" strokeLinecap="round" />
                <circle cx="24" cy="29" r="3.2" fill={RED} />
                <path d="M14 18.5L15.8 20.2M24 14V16.5M34 18.5L32.2 20.2" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
              </>
            );
          case "natural_falling_objects":
            return (
              <>
                <path d="M10 31L14 25H27L31 30.5H36C37.5 30.5 38.5 31.5 38.5 33V36.5H8V32.8C8 31.8 8.8 31 10 31Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" strokeLinejoin="round" />
                <circle cx="14.5" cy="37" r="2.8" fill="#FFFFFF" stroke={BLK} strokeWidth="2" />
                <circle cx="32" cy="37" r="2.8" fill="#FFFFFF" stroke={BLK} strokeWidth="2" />
                <path d="M11 12.5L31 19.5M19 10.5L23.5 16.8M27 11.5L29 18.5" stroke={BLK} strokeWidth="2.6" strokeLinecap="round" />
                <path d="M24 20V23.5M20 21.5L24 24.5L28 21.5" stroke={RED} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "side_mirror_protection":
            return (
              <>
                <path d="M12 29L16 36H22L19 28" fill={BLK} />
                <path d="M12 16.5C12 13.8 14.2 12 17.5 12H33.5C36.8 12 39 14.5 39 18V25C39 27.8 36.8 29.8 33.5 29.8H16C13.5 29.8 12 27.8 12 25V16.5Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" strokeLinejoin="round" />
                <path d="M23 14.5L27 20L24 23L29.5 27.5" stroke={RED} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "document_replacement":
            return (
              <>
                <rect x="7.5" y="12.5" width="33" height="23" rx="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <circle cx="16.5" cy="21" r="3.2" fill={BLK} />
                <path d="M11.5 29.5C11.5 26.8 13.8 25.5 16.5 25.5C19.2 25.5 21.5 26.8 21.5 29.5" fill="none" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <line x1="25" y1="19" x2="35.5" y2="19" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <line x1="25" y1="24" x2="35.5" y2="24" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <circle cx="32.5" cy="30.5" r="5" fill={RED} stroke="#FFFFFF" strokeWidth="1.3" />
              </>
            );
          case "total_loss_theft_allowance":
            return (
              <>
                <path d="M8 26.5L12 20H25L29 25.5H34C35.5 25.5 36.5 26.5 36.5 28V32.5H7.5V28C7.5 27.2 7.7 26.8 8 26.5Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.3" strokeLinejoin="round" />
                <circle cx="13.5" cy="33" r="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.1" />
                <circle cx="30" cy="33" r="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.1" />
                <circle cx="35" cy="17" r="7" fill={RED} stroke="#FFFFFF" strokeWidth="1.4" />
                <path d="M35 13.8V20.2M31.8 17H38.2" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
              </>
            );
          case "flood_relief_allowance":
            return (
              <>
                <path d="M12 27.5C13 23 16 21 20 21H28C32 21 34.5 23 35.5 27.5" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <path d="M7 31.5Q11.5 28.5 16 31.5T25 31.5T34 31.5T41 31.5" fill="none" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
                <path d="M9 37Q13 34.2 17 37T25 37T33 37T39 37" fill="none" stroke={BLK} strokeWidth="2.1" strokeLinecap="round" />
                <circle cx="24" cy="15" r="6.8" fill={RED} stroke="#FFFFFF" strokeWidth="1.3" />
                <text x="24" y="18.2" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="9" fontWeight="900" fill="#FFFFFF">$</text>
              </>
            );
          case "personal_belongings_theft":
            return (
              <>
                <rect x="11" y="18.5" width="26" height="19" rx="3" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <path d="M18.5 18.5V15C18.5 13.3 19.8 12 21.5 12H26.5C28.2 12 29.5 13.3 29.5 15V18.5" fill="none" stroke={BLK} strokeWidth="2.4" />
                <line x1="11" y1="25.5" x2="37" y2="25.5" stroke={BLK} strokeWidth="2" />
                <rect x="21.5" y="23.5" width="5" height="4.5" rx="1" fill={RED} />
                <path d="M34 10.5L36.5 14.5L40.5 12.5" fill="none" stroke={RED} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "pillion":
            return (
              <>
                <circle cx="13.5" cy="32.5" r="5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <circle cx="34.5" cy="32.5" r="5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <path d="M13.5 32.5L21.5 23.5H30L34.5 32.5M26 23.5L28.5 18H32" fill="none" stroke={BLK} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="25.5" cy="14" r="3" fill={BLK} />
                <circle cx="17" cy="15.5" r="3.2" fill={RED} />
                <path d="M15.5 19.5L19.5 23" stroke={RED} strokeWidth="2.6" strokeLinecap="round" />
              </>
            );
          case "daily_hospital_income":
            return (
              <>
                <rect x="11" y="13.5" width="22" height="24.5" rx="2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
                <path d="M22 17.5V24.5M18.5 21H25.5" stroke={RED} strokeWidth="2.6" strokeLinecap="round" />
                <rect x="18.5" y="29.5" width="7" height="8.5" fill={BLK} />
                <circle cx="35.5" cy="32.5" r="6.8" fill={RED} stroke="#FFFFFF" strokeWidth="1.3" />
                <text x="35.5" y="35.6" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="8.5" fontWeight="900" fill="#FFFFFF">$</text>
              </>
            );
          case "double_indemnity":
            return (
              <>
                <path d="M24 9L37.5 13.5V23.8C37.5 32 31.6 37.6 24 40C16.4 37.6 10.5 32 10.5 23.8V13.5L24 9Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.6" strokeLinejoin="round" />
                <text x="24" y="28.2" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="13" fontWeight="900" fill={RED}>2X</text>
              </>
            );
          case "medical_expenses":
            return (
              <>
                <rect x="9" y="15.5" width="30" height="22" rx="3.2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <path d="M18.5 15.5V12.5C18.5 11.1 19.6 10 21 10H27C28.4 10 29.5 11.1 29.5 12.5V15.5" fill="none" stroke={BLK} strokeWidth="2.4" />
                <path d="M24 20.5V32.5M18 26.5H30" stroke={RED} strokeWidth="3.2" strokeLinecap="round" />
              </>
            );
          case "permanent_disablement":
            return (
              <>
                <path d="M24 9L37 13.5V23.8C37 31.8 31.4 37.4 24 39.8C16.6 37.4 11 31.8 11 23.8V13.5L24 9Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" strokeLinejoin="round" />
                <path d="M15 24.5H19.5L22 19L25.5 29.5L28 24.5H33" fill="none" stroke={RED} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "ev_charging_bodily_injury":
            return (
              <>
                <circle cx="16.5" cy="14.5" r="3.8" fill={BLK} />
                <path d="M10.5 28C10.5 22.8 13.2 20.5 16.5 20.5C19.8 20.5 22.5 22.8 22.5 28V36H10.5V28Z" fill={BLK} />
                <path d="M33 11L27.5 21H32.5L30.5 29.5L37.5 18.5H32.2L33 11Z" fill={RED} />
                <path d="M27 36H38" stroke={BLK} strokeWidth="2.3" strokeLinecap="round" />
              </>
            );
          case "ev_home_content_fire":
            return (
              <>
                <path d="M8.5 22L24 10L39.5 22V37.5H8.5V22Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" strokeLinejoin="round" />
                <path d="M24 18.5C27 22.5 30 25.5 30 29.2A6 6 0 0 1 18 29.2C18 26.2 19.8 23.8 21.6 22C21.6 23.8 22.8 24.8 24 24.8C24 22.5 24 20.5 24 18.5Z" fill={RED} />
              </>
            );
          case "lonpac_ev_smart_pack":
            return (
              <>
                <path d="M9 28A15 15 0 1 1 39 28Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <path d="M12.5 31L15.5 25.5H27L30.5 30H35C36.2 30 37 31 37 32V36H11V32.5C11 31.8 11.7 31 12.5 31Z" fill={BLK} />
                <circle cx="16.5" cy="36.5" r="2.6" fill="#FFFFFF" stroke={BLK} strokeWidth="2" />
                <circle cx="31.5" cy="36.5" r="2.6" fill="#FFFFFF" stroke={BLK} strokeWidth="2" />
                <path d="M25.5 11.5L21 18.2H24.6L23.2 23.5L28 16.6H24.4L25.5 11.5Z" fill={RED} />
              </>
            );
          case "attached_trailers":
            return (
              <>
                <rect x="7.5" y="16" width="21" height="15" rx="2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
                <circle cx="18" cy="33" r="3.6" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
                <path d="M28.5 28H37.5V24.5" fill="none" stroke={RED} strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="37.5" cy="23.5" r="2.6" fill={RED} />
              </>
            );
          case "cargo_protection":
            return (
              <>
                <rect x="9" y="13" width="24" height="23" rx="2" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
                <line x1="9" y1="20" x2="33" y2="20" stroke={BLK} strokeWidth="2.2" />
                <line x1="21" y1="13" x2="21" y2="36" stroke={BLK} strokeWidth="2" />
                <path d="M34 22.5L40.5 25V30.5C40.5 34.5 37.8 37.2 34 38.6C30.2 37.2 27.5 34.5 27.5 30.5V25L34 22.5Z" fill={RED} stroke="#FFFFFF" strokeWidth="1.3" />
              </>
            );
          case "commercial_driver_crew_pa":
            return (
              <>
                <circle cx="16.5" cy="16" r="3.8" fill={BLK} />
                <path d="M9.5 32C9.5 27 12.5 24.5 16.5 24.5C20.5 24.5 23.5 27 23.5 32" fill="none" stroke={BLK} strokeWidth="2.4" strokeLinecap="round" />
                <circle cx="28.5" cy="17.5" r="3.4" fill={BLK} />
                <path d="M23 32C23 28 25.5 25.5 28.5 25.5C31.5 25.5 34 28 34 32" fill="none" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <circle cx="35.5" cy="31" r="6.8" fill={RED} stroke="#FFFFFF" strokeWidth="1.3" />
                <path d="M35.5 27.8V34.2M32.3 31H38.7" stroke="#FFFFFF" strokeWidth="2.1" strokeLinecap="round" />
              </>
            );
          case "private_car_365":
            return (
              <>
                <rect x="9.5" y="18.5" width="29" height="19" rx="2.5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" />
                <rect x="7.5" y="13.5" width="33" height="5.5" rx="1.5" fill={BLK} />
                <path d="M24 9.5C21 9.5 19.5 11.2 19.5 13.5H28.5C28.5 11.2 27 9.5 24 9.5Z" fill={RED} />
                <text x="24" y="31.5" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="10.5" fontWeight="900" fill={RED}>365</text>
              </>
            );
          case "smart_driver_pa":
            return (
              <>
                <circle cx="24" cy="24" r="14.5" fill="#FFFFFF" stroke={BLK} strokeWidth="3.2" />
                <path d="M10.5 22.5H37.5M24 25V38.5" stroke={BLK} strokeWidth="2.8" strokeLinecap="round" />
                <circle cx="24" cy="24" r="5.2" fill={RED} />
              </>
            );
          case "motor_pa_plus":
            return (
              <>
                <path d="M22 9L34 13V23C34 30.5 28.8 36 22 38.5C15.2 36 10 30.5 10 23V13L22 9Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <text x="22" y="27.5" textAnchor="middle" fontFamily="Arial,sans-serif" fontSize="11" fontWeight="900" fill={BLK}>PA</text>
                <circle cx="35.5" cy="32" r="7" fill={RED} stroke="#FFFFFF" strokeWidth="1.4" />
                <path d="M35.5 28.6V35.4M32.1 32H38.9" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
              </>
            );
          case "oto_360":
            return (
              <>
                <path d="M9.5 20A15.5 15.5 0 0 1 38.5 20" fill="none" stroke={RED} strokeWidth="2.6" strokeLinecap="round" />
                <polyline points="34.5,14.5 39,20.5 33,21.5" fill="none" stroke={RED} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M38.5 29A15.5 15.5 0 0 1 9.5 29" fill="none" stroke={RED} strokeWidth="2.6" strokeLinecap="round" />
                <polyline points="13.5,34.5 9,28.5 15,27.5" fill="none" stroke={RED} strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M14.5 25.5L17 20.5H29L32 25.5V29.5H14.5V25.5Z" fill={BLK} />
              </>
            );
          case "driver_passenger_protector":
            return (
              <>
                <path d="M8 22A16 16 0 0 1 40 22Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <circle cx="18" cy="29" r="3" fill={BLK} />
                <circle cx="30" cy="29" r="3" fill={BLK} />
                <path d="M13 37C13 34 15.2 32.5 18 32.5C20.8 32.5 23 34 23 37M25 37C25 34 27.2 32.5 30 32.5C32.8 32.5 35 34 35 37" fill="none" stroke={BLK} strokeWidth="2.2" strokeLinecap="round" />
                <circle cx="24" cy="14.5" r="3.8" fill={RED} />
              </>
            );
          case "motorshield_bundle":
            return (
              <>
                <path d="M24 8.5L38 13.5V24C38 32.5 32 38 24 40.5C16 38 10 32.5 10 24V13.5L24 8.5Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.6" strokeLinejoin="round" />
                <path d="M24 13.5L33.5 16.8V24C33.5 29.8 29.5 33.8 24 35.8C18.5 33.8 14.5 29.8 14.5 24V16.8L24 13.5Z" fill={BLK} />
                <path d="M24 18.5L25.8 22.5L30 23L26.8 25.8L27.8 30L24 27.8L20.2 30L21.2 25.8L18 23L22.2 22.5Z" fill={RED} />
              </>
            );
          case "sompo_motor_nhancer":
            return (
              <>
                <rect x="9.5" y="10.5" width="29" height="27" rx="5" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" />
                <path d="M16.5 23L24 15.5L31.5 23" fill="none" stroke={RED} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M16.5 31L24 23.5L31.5 31" fill="none" stroke={BLK} strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
          case "auto_buddy_malaysia":
            return (
              <>
                <circle cx="17.5" cy="18" r="4" fill={BLK} />
                <circle cx="30.5" cy="18" r="4" fill={BLK} />
                <path d="M10 34C10 28 13.2 25 17.5 25C20.2 25 22.5 26.5 24 28.8C25.5 26.5 27.8 25 30.5 25C34.8 25 38 28 38 34" fill="none" stroke={BLK} strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="24" cy="14" r="4.2" fill={RED} />
              </>
            );
          case "motor_easy":
            return (
              <>
                <path d="M14 38L19.5 16H28.5L34 38Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.4" strokeLinejoin="round" />
                <path d="M24 21V24.5M24 28.5V33" stroke={BLK} strokeWidth="2.4" strokeLinecap="round" />
                <path d="M24 8.5C20.5 8.5 18 11 18 14.2C18 18.2 24 22.5 24 22.5C24 22.5 30 18.2 30 14.2C30 11 27.5 8.5 24 8.5Z" fill={RED} stroke="#FFFFFF" strokeWidth="1.3" />
                <circle cx="24" cy="14" r="2" fill="#FFFFFF" />
              </>
            );
          default:
            return (
              <>
                <path d="M24 9L37 13.5V23.8C37 31.8 31.4 37.4 24 39.8C16.6 37.4 11 31.8 11 23.8V13.5L24 9Z" fill="#FFFFFF" stroke={BLK} strokeWidth="2.5" strokeLinejoin="round" />
                <path d="M18.5 24.2L22.2 27.8L30 19.8" stroke={RED} strokeWidth="2.7" strokeLinecap="round" strokeLinejoin="round" />
              </>
            );
        }
      })()}
    </svg>
  );
}

