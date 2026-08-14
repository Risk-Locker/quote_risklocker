import { redirect } from "next/navigation";

export default function LegacyOurSpecialsRedirect() {
  // RL-DISABLED active-our-specials-ui — disabled 2026-08-14; legacy data
  // remains readable through the hidden compatibility catalog only.
  redirect("/builder/benefits");
}
