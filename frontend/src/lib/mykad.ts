/**
 * Malaysian Identity Card (MyKad) utility
 * Decodes the birth date and calculates age from Malaysian 12-digit IC numbers (YYMMDD-PB-###G).
 */

export interface DecodedMyKad {
  isValid: boolean;
  birthDate: Date | null;
  formattedDob: string | null;
  age: number | null;
  gender: "Male" | "Female" | null;
}

export function decodeMalaysianIC(rawIc: string | null | undefined): DecodedMyKad {
  if (!rawIc) {
    return { isValid: false, birthDate: null, formattedDob: null, age: null, gender: null };
  }

  // Strip dashes, spaces, and punctuation
  const cleaned = rawIc.replace(/[^0-9]/g, "").trim();

  // Must have at least 6 digits to decode birthday, normally 12 digits
  if (cleaned.length < 6) {
    return { isValid: false, birthDate: null, formattedDob: null, age: null, gender: null };
  }

  const yyStr = cleaned.slice(0, 2);
  const mmStr = cleaned.slice(2, 4);
  const ddStr = cleaned.slice(4, 6);

  const yy = parseInt(yyStr, 10);
  const mm = parseInt(mmStr, 10);
  const dd = parseInt(ddStr, 10);

  if (isNaN(yy) || isNaN(mm) || isNaN(dd)) {
    return { isValid: false, birthDate: null, formattedDob: null, age: null, gender: null };
  }

  if (mm < 1 || mm > 12 || dd < 1 || dd > 31) {
    return { isValid: false, birthDate: null, formattedDob: null, age: null, gender: null };
  }

  // Century inference: Malaysian IC registered drivers.
  // Values >= 35 are typically 1900s (e.g. 88 -> 1988), <= 34 are 2000s (e.g. 05 -> 2005)
  const fullYear = yy >= 35 ? 1900 + yy : 2000 + yy;

  const birthDate = new Date(Date.UTC(fullYear, mm - 1, dd));

  // Verify date validity (e.g. leap year, 30-day months)
  if (
    birthDate.getUTCFullYear() !== fullYear ||
    birthDate.getUTCMonth() !== mm - 1 ||
    birthDate.getUTCDate() !== dd
  ) {
    return { isValid: false, birthDate: null, formattedDob: null, age: null, gender: null };
  }

  // Calculate age
  const today = new Date();
  let age = today.getFullYear() - fullYear;
  const monthDiff = today.getMonth() - (mm - 1);
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dd)) {
    age--;
  }

  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
  ];
  const formattedDob = `${String(dd).padStart(2, "0")} ${months[mm - 1]} ${fullYear}`;

  // Gender from 12th digit if available (odd = male, even = female)
  let gender: "Male" | "Female" | null = null;
  if (cleaned.length >= 12) {
    const lastDigit = parseInt(cleaned[11], 10);
    if (!isNaN(lastDigit)) {
      gender = lastDigit % 2 !== 0 ? "Male" : "Female";
    }
  }

  return {
    isValid: true,
    birthDate,
    formattedDob,
    age: Math.max(0, age),
    gender,
  };
}
