import * as React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ProcessIcon, resolveProcessIcon } from "../../src/presentation/processIcons";

describe("resolveProcessIcon", () => {
  it("resolves former brand names to the neutral fallback", () => {
    for (const name of [
      "python",
      "python3",
      "Python3.11",
      "brave",
      "Docker",
      "firefox",
      "openjdk",
      "spotify",
    ]) {
      const resolved = resolveProcessIcon(name);
      expect(resolved.kind).toBe("fallback");
    }
  });

  it("resolves a formerly branded executable to a neutral icon without assets", () => {
    const resolved = resolveProcessIcon("python");
    expect(resolved.kind).toBe("fallback");
    if (resolved.kind === "fallback") {
      expect(resolved.icon).toBeDefined();
    }
  });

  it("resolves exact Brave aliases to the neutral fallback", () => {
    for (const name of ["brave", "brave-browser"]) {
      const resolved = resolveProcessIcon(name);
      expect(resolved.kind).toBe("fallback");
    }
  });

  it("resolves exact Docker aliases to the neutral fallback", () => {
    for (const name of ["docker", "dockerd", "com.docker.backend"]) {
      const resolved = resolveProcessIcon(name);
      expect(resolved.kind).toBe("fallback");
    }
  });

  it("resolves exact Firefox aliases to the neutral fallback", () => {
    for (const name of ["firefox", "firefox-esr", "firefox-bin", "firefox-elf-firefox"]) {
      const resolved = resolveProcessIcon(name);
      expect(resolved.kind).toBe("fallback");
    }
  });

  it("resolves python versioned executables to the neutral fallback", () => {
    for (const name of ["python", "python3", "python3.11", "python 3"]) {
      const resolved = resolveProcessIcon(name);
      expect(resolved.kind).toBe("fallback");
    }
  });

  it("resolves explicit Java/OpenJDK names to the neutral fallback", () => {
    for (const name of ["openjdk", "openjdk java", "java openjdk", "java-openjdk", "java9"]) {
      const resolved = resolveProcessIcon(name);
      expect(resolved.kind).toBe("fallback");
    }
  });

  it("resolves GNOME Terminal exact name to the neutral fallback", () => {
    const resolved = resolveProcessIcon("gnome-terminal");
    expect(resolved.kind).toBe("fallback");
  });

  it("falls back for generic or misleading names", () => {
    for (const name of [
      "terminal",
      "java",
      "python-variant",
      "code",
      "code-insiders",
      "vscode",
      "systemd",
    ]) {
      const resolved = resolveProcessIcon(name);
      expect(resolved.kind).toBe("fallback");
    }
  });

  it("does not resolve an empty name to a brand icon", () => {
    expect(resolveProcessIcon("").kind).toBe("fallback");
    expect(resolveProcessIcon("   ").kind).toBe("fallback");
  });

  it("renders the neutral fallback for a formerly branded name", () => {
    render(React.createElement(ProcessIcon, { name: "python", "data-testid": "proc-icon" }));
    const icon = screen.getByTestId("proc-icon");
    expect(icon.tagName.toLowerCase()).toBe("svg");
    expect(icon.getAttribute("aria-hidden")).toBe("true");
  });

  it("renders fallback for unknown name", () => {
    render(React.createElement(ProcessIcon, { name: "systemd", "data-testid": "proc-icon-2" }));
    const icon = screen.getByTestId("proc-icon-2");
    expect(icon.tagName.toLowerCase()).toBe("svg");
  });
});
