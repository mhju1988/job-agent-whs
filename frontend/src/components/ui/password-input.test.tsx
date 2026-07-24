import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { PasswordInput } from "./password-input";

afterEach(cleanup);

function getInput(): HTMLInputElement {
  return screen.getByLabelText("Password", { selector: "input" }) as HTMLInputElement;
}

describe("PasswordInput", () => {
  it("masks the value by default", () => {
    render(<PasswordInput id="pw" aria-label="Password" />);
    expect(getInput().type).toBe("password");
  });

  it("reveals the value when the toggle is clicked", () => {
    render(<PasswordInput id="pw" aria-label="Password" />);
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(getInput().type).toBe("text");
  });

  it("masks the value again on a second click", () => {
    render(<PasswordInput id="pw" aria-label="Password" />);
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(getInput().type).toBe("password");
  });

  it("reports its state to assistive tech via aria-pressed", () => {
    render(<PasswordInput id="pw" aria-label="Password" />);
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Hide password" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
  });

  it("does not submit the surrounding form", () => {
    // A bare <button> inside a <form> defaults to type="submit", which would
    // sign the user in every time they peeked at their password.
    render(<PasswordInput id="pw" aria-label="Password" />);
    expect(screen.getByRole("button", { name: "Show password" }).getAttribute("type")).toBe(
      "button",
    );
  });

  it("forwards input props through to the underlying field", () => {
    render(
      <PasswordInput id="pw" aria-label="Password" autoComplete="new-password" required minLength={6} />,
    );
    const input = getInput();
    expect(input.id).toBe("pw");
    expect(input.autocomplete).toBe("new-password");
    expect(input.required).toBe(true);
    expect(input.minLength).toBe(6);
  });

  it("toggles each field independently", () => {
    // The signup page renders two of these; revealing one must not reveal the other.
    render(
      <>
        <PasswordInput id="pw" aria-label="Password" />
        <PasswordInput id="confirm" aria-label="Confirm password" />
      </>,
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Show password" })[0]);
    expect(getInput().type).toBe("text");
    expect(
      (screen.getByLabelText("Confirm password", { selector: "input" }) as HTMLInputElement).type,
    ).toBe("password");
  });

  it("stays controlled by the caller", () => {
    const seen: string[] = [];
    render(
      <PasswordInput
        id="pw"
        aria-label="Password"
        value="hunter2"
        onChange={(e) => seen.push(e.target.value)}
      />,
    );
    expect(getInput().value).toBe("hunter2");
    fireEvent.change(getInput(), { target: { value: "hunter3" } });
    expect(seen).toEqual(["hunter3"]);
  });
});
