import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { GuestOnly, Protected } from "./guards";

let auth;
vi.mock("../context/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../pages/Onboarding", () => ({ default: () => <p>Set up your household</p> }));

const renderAt = (path, ui) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path="/login" element={<p>Login page</p>} />
      <Route path="/" element={<p>Home page</p>} />
      <Route path="/secret" element={ui} />
    </Routes>
  </MemoryRouter>,
);

describe("Protected", () => {
  it("sends anonymous visitors to the login page", () => {
    auth = { user: null, household: null, loading: false, isAdmin: false };
    renderAt("/secret", <Protected><p>Secret</p></Protected>);
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });
  it("shows onboarding until a household exists", () => {
    auth = { user: { id: 1 }, household: null, loading: false, isAdmin: false };
    renderAt("/secret", <Protected needsHousehold><p>Secret</p></Protected>);
    expect(screen.getByText("Set up your household")).toBeInTheDocument();
  });
  it("keeps non-admins out of admin pages", () => {
    auth = { user: { id: 1 }, household: {}, loading: false, isAdmin: false };
    renderAt("/secret", <Protected adminOnly><p>Admin only</p></Protected>);
    expect(screen.getByText("Home page")).toBeInTheDocument();
  });
  it("lets admins in", () => {
    auth = { user: { id: 1 }, household: {}, loading: false, isAdmin: true };
    renderAt("/secret", <Protected adminOnly><p>Admin only</p></Protected>);
    expect(screen.getByText("Admin only")).toBeInTheDocument();
  });
  it("waits while the session is being restored", () => {
    auth = { user: null, household: null, loading: true, isAdmin: false };
    renderAt("/secret", <Protected><p>Secret</p></Protected>);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

describe("GuestOnly", () => {
  it("redirects a logged-in user away from the login page", () => {
    auth = { user: { id: 1 }, loading: false };
    renderAt("/secret", <GuestOnly><p>Login form</p></GuestOnly>);
    expect(screen.getByText("Home page")).toBeInTheDocument();
  });
});
