import * as React from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import androidStudioIcon from "../../src/assets/process-icons/android-studio.png?no-inline";
import audacityIcon from "../../src/assets/process-icons/audacity.png?no-inline";
import blenderIcon from "../../src/assets/process-icons/blender.png?no-inline";
import braveIcon from "../../src/assets/process-icons/brave.svg?no-inline";
import chatgptIcon from "../../src/assets/process-icons/chatgpt.svg?no-inline";
import chromeIcon from "../../src/assets/process-icons/chrome.svg?no-inline";
import chromiumIcon from "../../src/assets/process-icons/chromium.svg?no-inline";
import dbeaverIcon from "../../src/assets/process-icons/dbeaver.svg?no-inline";
import discordIcon from "../../src/assets/process-icons/discord.svg?no-inline";
import dockerIcon from "../../src/assets/process-icons/docker.svg?no-inline";
import eclipseIcon from "../../src/assets/process-icons/eclipse.png?no-inline";
import edgeIcon from "../../src/assets/process-icons/edge.svg?no-inline";
import evinceIcon from "../../src/assets/process-icons/evince.png?no-inline";
import filezillaIcon from "../../src/assets/process-icons/filezilla.svg?no-inline";
import firefoxIcon from "../../src/assets/process-icons/firefox.svg?no-inline";
import gimpIcon from "../../src/assets/process-icons/gimp.svg?no-inline";
import gitIcon from "../../src/assets/process-icons/git.svg?no-inline";
import githubDesktopIcon from "../../src/assets/process-icons/github-desktop.svg?no-inline";
import gnomeTerminalIcon from "../../src/assets/process-icons/gnome-terminal.png?no-inline";
import inkscapeIcon from "../../src/assets/process-icons/inkscape.svg?no-inline";
import insomniaIcon from "../../src/assets/process-icons/insomnia.svg?no-inline";
import intellijIcon from "../../src/assets/process-icons/intellij.png?no-inline";
import javaIcon from "../../src/assets/process-icons/java.svg?no-inline";
import jenkinsIcon from "../../src/assets/process-icons/jenkins.svg?no-inline";
import kdenliveIcon from "../../src/assets/process-icons/kdenlive.png?no-inline";
import kritaIcon from "../../src/assets/process-icons/krita.png?no-inline";
import kubernetesIcon from "../../src/assets/process-icons/kubernetes.svg?no-inline";
import libreofficeIcon from "../../src/assets/process-icons/libreoffice.png?no-inline";
import mongodbCompassIcon from "../../src/assets/process-icons/mongodb-compass.png?no-inline";
import mongodbIcon from "../../src/assets/process-icons/mongodb.svg?no-inline";
import mysqlIcon from "../../src/assets/process-icons/mysql.svg?no-inline";
import nautilusIcon from "../../src/assets/process-icons/nautilus.png?no-inline";
import netbeansIcon from "../../src/assets/process-icons/netbeans.svg?no-inline";
import nodeIcon from "../../src/assets/process-icons/node.svg?no-inline";
import obsIcon from "../../src/assets/process-icons/obs.svg?no-inline";
import ollamaIcon from "../../src/assets/process-icons/ollama.svg?no-inline";
import opencodeIcon from "../../src/assets/process-icons/opencode.svg?no-inline";
import operaIcon from "../../src/assets/process-icons/opera.svg?no-inline";
import pgadminIcon from "../../src/assets/process-icons/pgadmin.png?no-inline";
import postgresqlIcon from "../../src/assets/process-icons/postgresql.svg?no-inline";
import postmanIcon from "../../src/assets/process-icons/postman.png?no-inline";
import pycharmIcon from "../../src/assets/process-icons/pycharm.svg?no-inline";
import pythonIcon from "../../src/assets/process-icons/python.svg?no-inline";
import qemuIcon from "../../src/assets/process-icons/qemu.svg?no-inline";
import redisIcon from "../../src/assets/process-icons/redis.svg?no-inline";
import signalIcon from "../../src/assets/process-icons/signal.svg?no-inline";
import slackIcon from "../../src/assets/process-icons/slack.svg?no-inline";
import spotifyIcon from "../../src/assets/process-icons/spotify.svg?no-inline";
import steamIcon from "../../src/assets/process-icons/steam.svg?no-inline";
import teamsIcon from "../../src/assets/process-icons/teams.svg?no-inline";
import telegramIcon from "../../src/assets/process-icons/telegram.svg?no-inline";
import thunderbirdIcon from "../../src/assets/process-icons/thunderbird.png?no-inline";
import virtualboxIcon from "../../src/assets/process-icons/virtualbox.svg?no-inline";
import vivaldiIcon from "../../src/assets/process-icons/vivaldi.svg?no-inline";
import vlcIcon from "../../src/assets/process-icons/vlc.svg?no-inline";
import vscodeIcon from "../../src/assets/process-icons/vscode.svg?no-inline";
import vscodiumIcon from "../../src/assets/process-icons/vscodium.svg?no-inline";
import webstormIcon from "../../src/assets/process-icons/webstorm.png?no-inline";
import whatsappIcon from "../../src/assets/process-icons/whatsapp.svg?no-inline";
import zedIcon from "../../src/assets/process-icons/zed.png?no-inline";
import zoomIcon from "../../src/assets/process-icons/zoom.png?no-inline";
import {
  ProcessIcon,
  fallbackProcessIcon,
  processApps,
  resolveProcessApp,
  resolveProcessIcon,
} from "../../src/presentation/processIcons";

const assetSrc: Record<string, string> = {
  firefox: firefoxIcon,
  brave: braveIcon,
  chrome: chromeIcon,
  chromium: chromiumIcon,
  vscode: vscodeIcon,
  vscodium: vscodiumIcon,
  python: pythonIcon,
  java: javaIcon,
  node: nodeIcon,
  docker: dockerIcon,
  spotify: spotifyIcon,
  discord: discordIcon,
  slack: slackIcon,
  telegram: telegramIcon,
  zoom: zoomIcon,
  postgresql: postgresqlIcon,
  mysql: mysqlIcon,
  redis: redisIcon,
  mongodb: mongodbIcon,
  git: gitIcon,
  "github-desktop": githubDesktopIcon,
  postman: postmanIcon,
  insomnia: insomniaIcon,
  "gnome-terminal": gnomeTerminalIcon,
  nautilus: nautilusIcon,
  libreoffice: libreofficeIcon,
  evince: evinceIcon,
  vlc: vlcIcon,
  gimp: gimpIcon,
  intellij: intellijIcon,
  whatsapp: whatsappIcon,
  edge: edgeIcon,
  opera: operaIcon,
  vivaldi: vivaldiIcon,
  thunderbird: thunderbirdIcon,
  teams: teamsIcon,
  signal: signalIcon,
  obs: obsIcon,
  steam: steamIcon,
  blender: blenderIcon,
  inkscape: inkscapeIcon,
  krita: kritaIcon,
  audacity: audacityIcon,
  kdenlive: kdenliveIcon,
  filezilla: filezillaIcon,
  dbeaver: dbeaverIcon,
  pgadmin: pgadminIcon,
  "mongodb-compass": mongodbCompassIcon,
  pycharm: pycharmIcon,
  webstorm: webstormIcon,
  eclipse: eclipseIcon,
  netbeans: netbeansIcon,
  "android-studio": androidStudioIcon,
  virtualbox: virtualboxIcon,
  qemu: qemuIcon,
  jenkins: jenkinsIcon,
  kubernetes: kubernetesIcon,
  ollama: ollamaIcon,
  opencode: opencodeIcon,
  chatgpt: chatgptIcon,
  zed: zedIcon,
};

const assetKeys = Object.keys(assetSrc);

const EXPECTED_KEYS = [
  "firefox", "brave", "chrome", "chromium", "vscode", "vscodium", "python",
  "java", "node", "docker", "spotify", "discord", "slack", "telegram", "zoom",
  "postgresql", "mysql", "redis", "mongodb", "git", "github-desktop", "postman",
  "insomnia", "gnome-terminal", "nautilus", "libreoffice", "evince", "vlc", "gimp",
  "intellij", "whatsapp", "edge", "opera", "vivaldi", "thunderbird", "teams",
  "signal", "obs", "steam", "blender", "inkscape", "krita", "audacity", "kdenlive",
  "filezilla", "dbeaver", "pgadmin", "mongodb-compass", "pycharm", "webstorm",
  "eclipse", "netbeans", "android-studio", "virtualbox", "qemu", "jenkins",
  "kubernetes", "ollama", "opencode", "chatgpt", "zed",
];

/** Exact alias list per app: guards accidental prefix/substring additions. */
const EXPECTED_ALIASES: Record<string, readonly string[]> = {
  firefox: ["firefox", "firefox-bin", "firefox-esr"],
  brave: ["brave", "brave-browser"],
  chrome: ["chrome", "google-chrome", "chrome-stable"],
  chromium: ["chromium", "chromium-browser", "chromium-browse"],
  vscode: ["code", "code-oss"],
  vscodium: ["codium", "vscodium"],
  python: ["python", "python3", "python3.10", "python3.11", "python3.12", "python3.13", "python3.14"],
  java: ["java", "javaw"],
  node: ["node", "nodejs"],
  docker: ["docker", "dockerd", "docker-desktop"],
  spotify: ["spotify"],
  discord: ["discord"],
  slack: ["slack"],
  telegram: ["telegram", "telegram-desktop", "telegram-deskto"],
  zoom: ["zoom", "zoom.us"],
  postgresql: ["postgres", "postmaster"],
  mysql: ["mysqld"],
  redis: ["redis-server"],
  mongodb: ["mongod"],
  git: ["git"],
  "github-desktop": ["github-desktop", "githubdesktop"],
  postman: ["postman"],
  insomnia: ["insomnia"],
  "gnome-terminal": ["gnome-terminal", "gnome-terminal-server", "gnome-terminal-"],
  nautilus: ["nautilus"],
  libreoffice: ["soffice", "soffice.bin"],
  evince: ["evince", "evince-previewer", "evince-previewe"],
  vlc: ["vlc"],
  gimp: ["gimp", "gimp-3.0"],
  intellij: ["idea", "idea.sh"],
  whatsapp: [
    "whatsapp",
    "whatsapp-desktop",
    "whatsapp-deskto",
    "whatsapp-for-linux",
    "whatsapp-for-li",
    "whatsie",
  ],
  edge: [
    "microsoft-edge",
    "microsoft-edge-stable",
    "microsoft-edge-beta",
    "microsoft-edge-dev",
    "microsoft-edge-",
  ],
  opera: ["opera"],
  vivaldi: ["vivaldi"],
  thunderbird: ["thunderbird", "thunderbird-bin"],
  teams: ["teams", "teams-for-linux"],
  signal: ["signal-desktop"],
  obs: ["obs"],
  steam: ["steam", "steamwebhelper"],
  blender: ["blender"],
  inkscape: ["inkscape"],
  krita: ["krita"],
  audacity: ["audacity"],
  kdenlive: ["kdenlive"],
  filezilla: ["filezilla"],
  dbeaver: ["dbeaver"],
  pgadmin: ["pgadmin", "pgadmin4"],
  "mongodb-compass": ["mongodb-compass"],
  pycharm: [
    "pycharm",
    "pycharm.sh",
    "pycharm-community",
    "pycharm-communi",
    "pycharm-professional",
    "pycharm-profess",
  ],
  webstorm: ["webstorm", "webstorm.sh"],
  eclipse: ["eclipse"],
  netbeans: ["netbeans"],
  "android-studio": ["android-studio", "studio.sh"],
  virtualbox: ["virtualbox", "virtualboxvm", "vboxheadless", "vboxsvc"],
  qemu: [
    "qemu-system-x86_64",
    "qemu-system-x86",
    "qemu-system-i386",
    "qemu-system-i38",
    "qemu-system-aarch64",
    "qemu-system-aar",
    "qemu-kvm",
  ],
  jenkins: ["jenkins"],
  kubernetes: [
    "kubectl",
    "kubelet",
    "kube-apiserver",
    "kube-proxy",
    "kube-scheduler",
    "kube-controller-manager",
    "kube-controller",
  ],
  ollama: ["ollama", "ollama_llama_server", "ollama_llama_se"],
  opencode: ["opencode"],
  chatgpt: ["chatgpt", "chatgpt-desktop"],
  zed: ["zed"],
};

/** Per-mark dark-mode treatment; every other bundled mark must stay unfiltered. */
const EXPECTED_DARK: Record<string, string> = {
  slack: "dark:brightness-200",
  git: "dark:invert",
  "github-desktop": "dark:invert",
  steam: "dark:invert",
  inkscape: "dark:invert",
  qemu: "dark:invert",
  ollama: "dark:invert",
  opencode: "dark:invert",
  chatgpt: "dark:invert",
  signal: "dark:brightness-125",
};

const DARK_CLASSES = ["dark:invert", "dark:brightness-200", "dark:brightness-125"];

const UNFILTERED_KEYS = ["firefox", "vscodium", "chromium", "zoom", "blender", "zed"];

describe("processApps registry", () => {
  it("registers exactly 61 applications in the documented order", () => {
    expect(processApps).toHaveLength(61);
    expect(processApps.map((app) => app.key)).toEqual(EXPECTED_KEYS);
    expect(EXPECTED_KEYS).toHaveLength(61);
  });

  it("uses unique keys and unique lowercase aliases", () => {
    const keys = processApps.map((app) => app.key);
    expect(new Set(keys).size).toBe(keys.length);

    const aliases = processApps.flatMap((app) => app.aliases);
    expect(new Set(aliases).size).toBe(aliases.length);
    for (const alias of aliases) {
      expect(alias).toBe(alias.trim().toLowerCase());
    }
  });

  it("keeps the exact alias list unchanged in content and count", () => {
    expect(Object.keys(EXPECTED_ALIASES)).toEqual(EXPECTED_KEYS);
    expect(
      processApps.map((app) => [app.key, [...app.aliases]]),
    ).toEqual(EXPECTED_KEYS.map((key) => [key, [...(EXPECTED_ALIASES[key] ?? [])]]));
    expect(processApps.reduce((total, app) => total + app.aliases.length, 0)).toBe(130);
  });

  it("maps every alias back to its own application", () => {
    for (const app of processApps) {
      for (const alias of app.aliases) {
        expect(resolveProcessApp(alias)).toBe(app);
      }
    }
  });

  it("bundles all 61 applications with a truthy unique src", () => {
    expect(assetKeys).toHaveLength(61);
    for (const app of processApps) {
      expect(assetSrc[app.key]).toBeTruthy();
      expect(app.src).toBe(assetSrc[app.key]);
    }
    const srcs = processApps.map((app) => app.src);
    expect(srcs.every((src) => typeof src === "string" && src.length > 0)).toBe(true);
    expect(new Set(srcs).size).toBe(61);
  });

  it("resolves every alias to its brand source and exact key", () => {
    for (const app of processApps) {
      for (const alias of app.aliases) {
        expect(resolveProcessIcon(alias)).toEqual({
          kind: "brand",
          key: app.key,
          src: assetSrc[app.key],
          ...(app.darkClassName ? { darkClassName: app.darkClassName } : {}),
        });
      }
    }
  });

  it("normalizes case and surrounding whitespace only", () => {
    for (const name of ["Git", " GIT ", "Firefox", "  Chrome  ", "QEMU-SYSTEM-X86_64"]) {
      expect(resolveProcessIcon(name).kind).toBe("brand");
    }
  });
});

describe("resolveProcessIcon false positives and truncation", () => {
  it("stays neutral for lookalike, prefixed or suffix-only names", () => {
    for (const name of [
      "java9",
      "python-variant",
      "node-helper",
      "brave-fake",
      "gitk",
      "git-credential",
      "mygit",
      "codium-helper",
      "vscodium-fake",
      "vscode",
      "code-insiders",
      "chromium-helper",
      "qemu",
      "mysql-helper",
      "redis-cli",
      "mongod-helper",
      "kubectl-helper",
      "ollama2",
      "zed-helper",
      "pgadmin3",
      "teams-for-linux-helper",
      "blender-helper",
      "systemd",
      "terminal",
      "whatsapp-browser",
      "chrome-helper",
      "slackbot",
      "docker-compose",
      "signal-cli",
      "steamcmd",
      "openjdk",
      "com.docker.backend",
      "firefox-elf-firefox",
      "git.git",
      "python 3",
      "openjdk java",
      "java openjdk",
      "java-openjdk",
    ]) {
      const resolved = resolveProcessIcon(name);
      expect(resolved.kind, name).toBe("fallback");
      expect(resolved).toEqual({ kind: "fallback", icon: fallbackProcessIcon });
    }
  });

  it("resolves real asset aliases that are no longer neutral", () => {
    for (const name of [
      "firefox",
      "firefox-bin",
      "firefox-esr",
      "brave",
      "brave-browser",
      "docker",
      "dockerd",
      "docker-desktop",
      "python",
      "python3",
      "python3.11",
      "java",
      "chrome",
      "google-chrome",
      "chrome-stable",
      "node",
      "nodejs",
      "spotify",
      "code",
      "idea",
      "code-oss",
      "gnome-terminal",
    ]) {
      expect(resolveProcessIcon(name).kind, name).toBe("brand");
    }
  });

  it("does not resolve empty or whitespace-only names to a brand icon", () => {
    for (const name of ["", "   ", "\t\n"]) {
      expect(resolveProcessIcon(name)).toEqual({
        kind: "fallback",
        icon: fallbackProcessIcon,
      });
    }
  });

  it("handles 15-character comm truncations with exact aliases only", () => {
    const truncations: Array<[string, string]> = [
      ["telegram-deskto", "telegram"],
      ["whatsapp-deskto", "whatsapp"],
      ["whatsapp-for-li", "whatsapp"],
      ["gnome-terminal-", "gnome-terminal"],
      ["chromium-browse", "chromium"],
      ["microsoft-edge-", "edge"],
      ["pycharm-communi", "pycharm"],
      ["pycharm-profess", "pycharm"],
      ["evince-previewe", "evince"],
      ["qemu-system-x86", "qemu"],
      ["qemu-system-i38", "qemu"],
      ["qemu-system-aar", "qemu"],
      ["ollama_llama_se", "ollama"],
      ["kube-controller", "kubernetes"],
    ];
    for (const [alias, key] of truncations) {
      expect(alias.length, alias).toBe(15);
      expect(resolveProcessApp(alias)?.key, alias).toBe(key);
      expect(resolveProcessIcon(alias)).toMatchObject({ kind: "brand", key });
    }

    expect(resolveProcessApp("gnome-terminal-")?.key).toBe("gnome-terminal");
    expect(resolveProcessApp("chromium-browse")?.key).toBe("chromium");
    expect(resolveProcessApp("telegram-deskto")?.key).toBe("telegram");
    expect(resolveProcessApp("whatsapp-for-li")?.key).toBe("whatsapp");
  });

  it("does not resolve the uncorrected 16-character strings", () => {
    for (const name of [
      "pycharm-communit",
      "qemu-system-x86_",
      "qemu-system-aarc",
    ]) {
      expect(resolveProcessApp(name)).toBeUndefined();
      expect(resolveProcessIcon(name).kind, name).toBe("fallback");
    }
  });
});

describe("brand process icons", () => {
  it("maps Git, GitHub Desktop and VSCodium aliases to the bundled assets", () => {
    expect(resolveProcessIcon("git")).toEqual({
      kind: "brand",
      src: gitIcon,
      key: "git",
      darkClassName: "dark:invert",
    });
    expect(resolveProcessIcon("githubdesktop")).toEqual({
      kind: "brand",
      src: githubDesktopIcon,
      key: "github-desktop",
      darkClassName: "dark:invert",
    });
    expect(resolveProcessIcon("codium")).toEqual({
      kind: "brand",
      src: vscodiumIcon,
      key: "vscodium",
    });
    expect(resolveProcessIcon("vscodium")).toEqual({
      kind: "brand",
      src: vscodiumIcon,
      key: "vscodium",
    });
  });

  it("marks exactly the ten filtered marks for dark mode", () => {
    const themed = processApps.filter((app) => app.darkClassName).map((app) => app.key);
    expect(themed.sort()).toEqual(Object.keys(EXPECTED_DARK).sort());
    for (const app of processApps) {
      expect(app.darkClassName, app.key).toBe(EXPECTED_DARK[app.key]);
    }
  });

  it("keeps the full-colour marks free of dark filters", () => {
    for (const key of UNFILTERED_KEYS) {
      const app = processApps.find((entry) => entry.key === key);
      expect(app, key).toBeDefined();
      expect(app?.darkClassName, key).toBeUndefined();
      const resolved = resolveProcessIcon(app?.aliases[0] ?? key);
      expect(resolved.kind, key).toBe("brand");
      expect(resolved).not.toMatchObject({ darkClassName: expect.any(String) });
    }
  });
});

describe("ProcessIcon brand rendering", () => {
  it("renders a 16px decorative image with the dark-mode treatment", () => {
    render(
      React.createElement(ProcessIcon, {
        name: "git",
        className: "h-4 w-4",
        "data-testid": "brand-icon",
      }),
    );
    const icon = screen.getByTestId("brand-icon");
    expect(icon.tagName.toLowerCase()).toBe("img");
    expect(icon).toHaveAttribute("src", gitIcon);
    expect(icon).toHaveAttribute("width", "16");
    expect(icon).toHaveAttribute("height", "16");
    expect(icon).toHaveAttribute("alt", "");
    expect(icon).toHaveAttribute("aria-hidden", "true");
    const className = icon.getAttribute("class") ?? "";
    expect(className).toContain("h-4");
    expect(className).toContain("dark:invert");
    expect(className).toContain("object-contain");
    expect(className).not.toContain("dark:brightness-0");
  });

  it("keeps the VSCodium colours instead of inverting the mark", () => {
    render(
      React.createElement(ProcessIcon, {
        name: "vscodium",
        className: "h-4 w-4",
        "data-testid": "brand-icon",
      }),
    );
    const icon = screen.getByTestId("brand-icon");
    expect(icon.tagName.toLowerCase()).toBe("img");
    expect(icon).toHaveAttribute("src", vscodiumIcon);
    const className = icon.getAttribute("class") ?? "";
    expect(className).toContain("h-4");
    expect(className).toContain("object-contain");
    expect(className).not.toContain("dark:invert");
    expect(className).not.toContain("dark:brightness-0");
  });

  it("applies the exact dark treatment per mark", () => {
    expect(Object.keys(EXPECTED_DARK)).toHaveLength(10);
    for (const [key, expected] of Object.entries(EXPECTED_DARK)) {
      const app = processApps.find((entry) => entry.key === key);
      expect(app, key).toBeDefined();
      // Render through a real alias, not the registry key ("qemu"/"signal" have none).
      const name = app?.aliases[0] ?? key;
      const { unmount } = render(
        React.createElement(ProcessIcon, { name, "data-testid": "themed-icon" }),
      );
      const className = screen.getByTestId("themed-icon").getAttribute("class") ?? "";
      expect(className, name).toContain(expected);
      for (const other of DARK_CLASSES) {
        if (other !== expected) {
          expect(className, `${name} must not use ${other}`).not.toContain(other);
        }
      }
      unmount();
    }
    for (const name of UNFILTERED_KEYS) {
      const { unmount } = render(
        React.createElement(ProcessIcon, { name, "data-testid": "plain-icon" }),
      );
      const className = screen.getByTestId("plain-icon").getAttribute("class") ?? "";
      for (const darkClass of DARK_CLASSES) {
        expect(className, `${name} must not use ${darkClass}`).not.toContain(darkClass);
      }
      unmount();
    }
  });

  it("renders all 61 brands as 16x16 decorative contained images", () => {
    expect(processApps.filter((app) => app.src)).toHaveLength(61);
    for (const app of processApps) {
      const { unmount } = render(
        React.createElement(ProcessIcon, {
          name: app.aliases[0],
          "data-testid": "all-brand",
        }),
      );
      const icon = screen.getByTestId("all-brand");
      expect(icon.tagName.toLowerCase(), app.key).toBe("img");
      expect(icon, app.key).toHaveAttribute("src", assetSrc[app.key]);
      expect(icon, app.key).toHaveAttribute("alt", "");
      expect(icon, app.key).toHaveAttribute("aria-hidden", "true");
      expect(icon, app.key).toHaveAttribute("width", "16");
      expect(icon, app.key).toHaveAttribute("height", "16");
      const className = icon.getAttribute("class") ?? "";
      expect(className, app.key).toContain("object-contain");
      if (app.darkClassName) {
        expect(className, app.key).toContain(app.darkClassName);
      } else {
        for (const darkClass of DARK_CLASSES) {
          expect(className, `${app.key} must not use ${darkClass}`).not.toContain(darkClass);
        }
      }
      unmount();
    }
  });

  it("falls back per failed source and retries when the source changes", () => {
    const { rerender } = render(
      React.createElement(ProcessIcon, {
        name: "firefox",
        "data-testid": "source-icon",
      }),
    );
    const image = screen.getByTestId("source-icon");
    expect(image.tagName.toLowerCase()).toBe("img");
    fireEvent.error(image);
    expect(screen.getByTestId("source-icon").tagName.toLowerCase()).toBe("svg");

    rerender(
      React.createElement(ProcessIcon, {
        name: "chrome",
        "data-testid": "source-icon",
      }),
    );
    expect(screen.getByTestId("source-icon").tagName.toLowerCase()).toBe("img");

    rerender(
      React.createElement(ProcessIcon, {
        name: "firefox",
        "data-testid": "source-icon",
      }),
    );
    expect(screen.getByTestId("source-icon").tagName.toLowerCase()).toBe("img");
  });

  it("recovers a newly bundled icon after its own error", () => {
    const { rerender } = render(
      React.createElement(ProcessIcon, {
        name: "blender",
        "data-testid": "source-icon",
      }),
    );
    const image = screen.getByTestId("source-icon");
    expect(image.tagName.toLowerCase()).toBe("img");
    expect(image).toHaveAttribute("src", blenderIcon);
    fireEvent.error(image);
    expect(screen.getByTestId("source-icon").tagName.toLowerCase()).toBe("svg");

    // A different source still renders the real blender mark.
    rerender(
      React.createElement(ProcessIcon, {
        name: "zed",
        "data-testid": "source-icon",
      }),
    );
    expect(screen.getByTestId("source-icon")).toHaveAttribute("src", zedIcon);

    // Returning to blender retries exactly once.
    rerender(
      React.createElement(ProcessIcon, {
        name: "blender",
        "data-testid": "source-icon",
      }),
    );
    const retried = screen.getByTestId("source-icon");
    expect(retried.tagName.toLowerCase()).toBe("img");
    expect(retried).toHaveAttribute("src", blenderIcon);
  });

  it("does not retry the same failed source on rerender", () => {
    const { rerender } = render(
      React.createElement(ProcessIcon, {
        name: "firefox",
        "data-testid": "source-icon",
      }),
    );
    fireEvent.error(screen.getByTestId("source-icon"));
    expect(screen.getByTestId("source-icon").tagName.toLowerCase()).toBe("svg");

    rerender(
      React.createElement(ProcessIcon, {
        name: "firefox",
        "data-testid": "source-icon",
      }),
    );
    expect(screen.getByTestId("source-icon").tagName.toLowerCase()).toBe("svg");
  });

  it("keeps unknown process names on the neutral fallback icon", () => {
    render(
      React.createElement(ProcessIcon, {
        name: "definitely-not-an-app --verbose",
        "data-testid": "unknown-icon",
      }),
    );
    const icon = screen.getByTestId("unknown-icon");
    expect(icon.tagName.toLowerCase()).toBe("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon).not.toHaveAttribute("src");
  });
});
