import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Login } from "./AuthPages";

// A plain function the tests swap per case (avoids vi.fn reset quirks with rejecting mocks).
let loginImpl;
const calls = [];
vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ login: (...args) => { calls.push(args); return loginImpl(...args); } }),
}));

const setup = () => render(<MemoryRouter><Login /></MemoryRouter>);

describe("Login", () => {
  beforeEach(() => { calls.length = 0; loginImpl = async () => ({}); });

  it("submits the entered credentials", async () => {
    setup();
    await userEvent.type(screen.getByLabelText("Email"), "amina@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "ChangeMe123!");
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));
    expect(calls).toEqual([["amina@example.com", "ChangeMe123!"]]);
  });

  it("shows the server's message when the login fails", async () => {
    // Axios rejects with an Error carrying the HTTP response.
    const failure = Object.assign(new Error("Request failed with status code 401"),
      { response: { status: 401, data: { error: { message: "Invalid email or password" } } } });
    loginImpl = async () => { throw failure; };
    setup();
    await userEvent.type(screen.getByLabelText("Email"), "a@b.co");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });

  it("can fill the documented development demo account", async () => {
    setup();
    await userEvent.click(screen.getByText("Fill demo login"));
    expect(screen.getByLabelText("Email")).toHaveValue("demo@example.com");
    expect(screen.getByLabelText("Password")).toHaveValue("ChangeMe123!");
  });
});
