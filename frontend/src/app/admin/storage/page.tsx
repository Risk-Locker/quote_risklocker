import { redirect } from "next/navigation";

export default function AdminStorageRedirect() {
  redirect("/settings/storage");
}
