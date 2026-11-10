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

