// RL-DISABLED add_vehicle_deal_modal — disabled 2026-10-01; restore when modal deal entry is requested instead of direct marketing comparison intake
// Per user directive: any adding anywhere will take the user to the marketing comparison UI where the 3 columns layout is located.

export interface PersonInCharge {
  id: string;
  name: string;
  type: "subagent" | "company_personnel" | "client_self" | "external_contact";
  agency_group: string | null;
  commission_rate: number;
}

export function AddVehicleDealModal(_props: any) {
  return null;
}
