import { redirect } from "next/navigation";

export default function AdminChecksRedirect() {
  redirect("/settings/system-checks");
}
