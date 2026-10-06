import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/common";
import { useAuth } from "../context/AuthContext";
import { whenDate } from "../utils/format";

export default function Profile() {
  const { user, household, logout } = useAuth();
  const navigate = useNavigate();
  const rows = [["Name", user.name], ["Email", user.email], ["Role", user.role === "ADMIN" ? "Administrator" : "Household user"], ["Member since", whenDate(user.created_at)],
    ["Household", household ? `${household.household_name}${household.location ? `, ${household.location}` : ""} (${household.household_size} people)` : "Not set up yet"]];
  return (
    <>
      <PageHeader title="Profile" />
      <section className="panel max-w-2xl p-5">
        <dl className="grid grid-cols-[auto_1fr] gap-x-8 gap-y-3 text-sm">{rows.map(([k, v]) => <div key={k} className="contents"><dt className="text-mute">{k}</dt><dd>{v}</dd></div>)}</dl>
        <button className="btn-ghost mt-6" onClick={() => { logout(); navigate("/login"); }}><LogOut className="h-4 w-4" /> Log out</button>
      </section>
    </>
  );
}
