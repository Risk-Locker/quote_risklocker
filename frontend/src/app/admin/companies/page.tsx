import { redirect } from "next/navigation";

export default function AdminCompaniesRedirect() {
  redirect("/builder/companies");
}
