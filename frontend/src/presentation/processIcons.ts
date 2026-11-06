import { AppWindow } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import * as React from "react";
import { useEffect, useState } from "react";

import androidStudioIcon from "../assets/process-icons/android-studio.png?no-inline";
import audacityIcon from "../assets/process-icons/audacity.png?no-inline";
import blenderIcon from "../assets/process-icons/blender.png?no-inline";
import braveIcon from "../assets/process-icons/brave.svg?no-inline";
import chatgptIcon from "../assets/process-icons/chatgpt.svg?no-inline";
import chromeIcon from "../assets/process-icons/chrome.svg?no-inline";
import chromiumIcon from "../assets/process-icons/chromium.svg?no-inline";
import dbeaverIcon from "../assets/process-icons/dbeaver.svg?no-inline";
import discordIcon from "../assets/process-icons/discord.svg?no-inline";
import dockerIcon from "../assets/process-icons/docker.svg?no-inline";
import eclipseIcon from "../assets/process-icons/eclipse.png?no-inline";
import edgeIcon from "../assets/process-icons/edge.svg?no-inline";
import evinceIcon from "../assets/process-icons/evince.png?no-inline";
import filezillaIcon from "../assets/process-icons/filezilla.svg?no-inline";
import firefoxIcon from "../assets/process-icons/firefox.svg?no-inline";
import gimpIcon from "../assets/process-icons/gimp.svg?no-inline";
import gitIcon from "../assets/process-icons/git.svg?no-inline";
import githubDesktopIcon from "../assets/process-icons/github-desktop.svg?no-inline";
import gnomeTerminalIcon from "../assets/process-icons/gnome-terminal.png?no-inline";
import inkscapeIcon from "../assets/process-icons/inkscape.svg?no-inline";
import insomniaIcon from "../assets/process-icons/insomnia.svg?no-inline";
import intellijIcon from "../assets/process-icons/intellij.png?no-inline";
import javaIcon from "../assets/process-icons/java.svg?no-inline";
import jenkinsIcon from "../assets/process-icons/jenkins.svg?no-inline";
import kdenliveIcon from "../assets/process-icons/kdenlive.png?no-inline";
import kritaIcon from "../assets/process-icons/krita.png?no-inline";
import kubernetesIcon from "../assets/process-icons/kubernetes.svg?no-inline";
import libreofficeIcon from "../assets/process-icons/libreoffice.png?no-inline";
import mongodbCompassIcon from "../assets/process-icons/mongodb-compass.png?no-inline";
import mongodbIcon from "../assets/process-icons/mongodb.svg?no-inline";
import mysqlIcon from "../assets/process-icons/mysql.svg?no-inline";
import nautilusIcon from "../assets/process-icons/nautilus.png?no-inline";
import netbeansIcon from "../assets/process-icons/netbeans.svg?no-inline";
import nodeIcon from "../assets/process-icons/node.svg?no-inline";
import obsIcon from "../assets/process-icons/obs.svg?no-inline";
import ollamaIcon from "../assets/process-icons/ollama.svg?no-inline";
import opencodeIcon from "../assets/process-icons/opencode.svg?no-inline";
import operaIcon from "../assets/process-icons/opera.svg?no-inline";
import pgadminIcon from "../assets/process-icons/pgadmin.png?no-inline";
import postgresqlIcon from "../assets/process-icons/postgresql.svg?no-inline";
import postmanIcon from "../assets/process-icons/postman.png?no-inline";
import pycharmIcon from "../assets/process-icons/pycharm.svg?no-inline";
import pythonIcon from "../assets/process-icons/python.svg?no-inline";
import qemuIcon from "../assets/process-icons/qemu.svg?no-inline";
import redisIcon from "../assets/process-icons/redis.svg?no-inline";
import signalIcon from "../assets/process-icons/signal.svg?no-inline";
import slackIcon from "../assets/process-icons/slack.svg?no-inline";
import spotifyIcon from "../assets/process-icons/spotify.svg?no-inline";
import steamIcon from "../assets/process-icons/steam.svg?no-inline";
import teamsIcon from "../assets/process-icons/teams.svg?no-inline";
import telegramIcon from "../assets/process-icons/telegram.svg?no-inline";
import thunderbirdIcon from "../assets/process-icons/thunderbird.png?no-inline";
import virtualboxIcon from "../assets/process-icons/virtualbox.svg?no-inline";
import vivaldiIcon from "../assets/process-icons/vivaldi.svg?no-inline";
import vlcIcon from "../assets/process-icons/vlc.svg?no-inline";
import vscodeIcon from "../assets/process-icons/vscode.svg?no-inline";
import vscodiumIcon from "../assets/process-icons/vscodium.svg?no-inline";
import webstormIcon from "../assets/process-icons/webstorm.png?no-inline";
import whatsappIcon from "../assets/process-icons/whatsapp.svg?no-inline";
import zedIcon from "../assets/process-icons/zed.png?no-inline";
import zoomIcon from "../assets/process-icons/zoom.png?no-inline";

export type ProcessAppKey =
  | "firefox"
  | "brave"
  | "chrome"
  | "chromium"
  | "vscode"
  | "vscodium"
  | "python"
  | "java"
  | "node"
  | "docker"
  | "spotify"
  | "discord"
  | "slack"
  | "telegram"
  | "zoom"
  | "postgresql"
  | "mysql"
  | "redis"
  | "mongodb"
  | "git"
  | "github-desktop"
  | "postman"
  | "insomnia"
  | "gnome-terminal"
  | "nautilus"
  | "libreoffice"
  | "evince"
  | "vlc"
  | "gimp"
  | "intellij"
  | "whatsapp"
  | "edge"
  | "opera"
  | "vivaldi"
  | "thunderbird"
  | "teams"
  | "signal"
  | "obs"
  | "steam"
  | "blender"
  | "inkscape"
  | "krita"
  | "audacity"
  | "kdenlive"
  | "filezilla"
  | "dbeaver"
  | "pgadmin"
  | "mongodb-compass"
  | "pycharm"
  | "webstorm"
  | "eclipse"
  | "netbeans"
  | "android-studio"
  | "virtualbox"
  | "qemu"
  | "jenkins"
  | "kubernetes"
  | "ollama"
  | "opencode"
  | "chatgpt"
  | "zed";

export type ProcessAppDefinition = {
  readonly key: ProcessAppKey;
  readonly name: string;
  readonly aliases: readonly string[];
  readonly src?: string;
  readonly darkClassName?: string;
};

/**
 * Process applications and their explicitly verified exact aliases.
 * No prefix, substring or path matching: every other name stays neutral.
 * `src` is present only for applications with a bundled, licensed asset;
 * `darkClassName` carries the per-mark dark-theme treatment of that asset.
 */
export const processApps: readonly ProcessAppDefinition[] = [
  { key: "firefox", name: "Firefox", aliases: ["firefox", "firefox-bin", "firefox-esr"], src: firefoxIcon },
  { key: "brave", name: "Brave Browser", aliases: ["brave", "brave-browser"], src: braveIcon },
  { key: "chrome", name: "Google Chrome", aliases: ["chrome", "google-chrome", "chrome-stable"], src: chromeIcon },
  { key: "chromium", name: "Chromium", aliases: ["chromium", "chromium-browser", "chromium-browse"], src: chromiumIcon },
  { key: "vscode", name: "VS Code", aliases: ["code", "code-oss"], src: vscodeIcon },
  { key: "vscodium", name: "VSCodium", aliases: ["codium", "vscodium"], src: vscodiumIcon },
  { key: "python", name: "Python", aliases: ["python", "python3", "python3.10", "python3.11", "python3.12", "python3.13", "python3.14"], src: pythonIcon },
  { key: "java", name: "Java / OpenJDK", aliases: ["java", "javaw"], src: javaIcon },
  { key: "node", name: "Node.js", aliases: ["node", "nodejs"], src: nodeIcon },
  { key: "docker", name: "Docker", aliases: ["docker", "dockerd", "docker-desktop"], src: dockerIcon },
  { key: "spotify", name: "Spotify", aliases: ["spotify"], src: spotifyIcon },
  { key: "discord", name: "Discord", aliases: ["discord"], src: discordIcon },
  { key: "slack", name: "Slack", aliases: ["slack"], src: slackIcon, darkClassName: "dark:brightness-200" },
  { key: "telegram", name: "Telegram Desktop", aliases: ["telegram", "telegram-desktop", "telegram-deskto"], src: telegramIcon },
  { key: "zoom", name: "Zoom", aliases: ["zoom", "zoom.us"], src: zoomIcon },
  { key: "postgresql", name: "PostgreSQL", aliases: ["postgres", "postmaster"], src: postgresqlIcon },
  { key: "mysql", name: "MySQL", aliases: ["mysqld"], src: mysqlIcon },
  { key: "redis", name: "Redis", aliases: ["redis-server"], src: redisIcon },
  { key: "mongodb", name: "MongoDB", aliases: ["mongod"], src: mongodbIcon },
  { key: "git", name: "Git", aliases: ["git"], src: gitIcon, darkClassName: "dark:invert" },
  { key: "github-desktop", name: "GitHub Desktop", aliases: ["github-desktop", "githubdesktop"], src: githubDesktopIcon, darkClassName: "dark:invert" },
  { key: "postman", name: "Postman", aliases: ["postman"], src: postmanIcon },
  { key: "insomnia", name: "Insomnia", aliases: ["insomnia"], src: insomniaIcon },
  { key: "gnome-terminal", name: "GNOME Terminal", aliases: ["gnome-terminal", "gnome-terminal-server", "gnome-terminal-"], src: gnomeTerminalIcon },
  { key: "nautilus", name: "Nautilus", aliases: ["nautilus"], src: nautilusIcon },
  { key: "libreoffice", name: "LibreOffice", aliases: ["soffice", "soffice.bin"], src: libreofficeIcon },
  { key: "evince", name: "Evince", aliases: ["evince", "evince-previewer", "evince-previewe"], src: evinceIcon },
  { key: "vlc", name: "VLC", aliases: ["vlc"], src: vlcIcon },
  { key: "gimp", name: "GIMP", aliases: ["gimp", "gimp-3.0"], src: gimpIcon },
  { key: "intellij", name: "IntelliJ IDEA", aliases: ["idea", "idea.sh"], src: intellijIcon },
  { key: "whatsapp", name: "WhatsApp / Whatsie", aliases: ["whatsapp", "whatsapp-desktop", "whatsapp-deskto", "whatsapp-for-linux", "whatsapp-for-li", "whatsie"], src: whatsappIcon },
  { key: "edge", name: "Microsoft Edge", aliases: ["microsoft-edge", "microsoft-edge-stable", "microsoft-edge-beta", "microsoft-edge-dev", "microsoft-edge-"], src: edgeIcon },
  { key: "opera", name: "Opera", aliases: ["opera"], src: operaIcon },
  { key: "vivaldi", name: "Vivaldi", aliases: ["vivaldi"], src: vivaldiIcon },
  { key: "thunderbird", name: "Thunderbird", aliases: ["thunderbird", "thunderbird-bin"], src: thunderbirdIcon },
  { key: "teams", name: "Microsoft Teams", aliases: ["teams", "teams-for-linux"], src: teamsIcon },
  { key: "signal", name: "Signal Desktop", aliases: ["signal-desktop"], src: signalIcon, darkClassName: "dark:brightness-125" },
  { key: "obs", name: "OBS Studio", aliases: ["obs"], src: obsIcon },
  { key: "steam", name: "Steam", aliases: ["steam", "steamwebhelper"], src: steamIcon, darkClassName: "dark:invert" },
  { key: "blender", name: "Blender", aliases: ["blender"], src: blenderIcon },
  { key: "inkscape", name: "Inkscape", aliases: ["inkscape"], src: inkscapeIcon, darkClassName: "dark:invert" },
  { key: "krita", name: "Krita", aliases: ["krita"], src: kritaIcon },
  { key: "audacity", name: "Audacity", aliases: ["audacity"], src: audacityIcon },
  { key: "kdenlive", name: "Kdenlive", aliases: ["kdenlive"], src: kdenliveIcon },
  { key: "filezilla", name: "FileZilla", aliases: ["filezilla"], src: filezillaIcon },
  { key: "dbeaver", name: "DBeaver", aliases: ["dbeaver"], src: dbeaverIcon },
  { key: "pgadmin", name: "pgAdmin", aliases: ["pgadmin", "pgadmin4"], src: pgadminIcon },
  { key: "mongodb-compass", name: "MongoDB Compass", aliases: ["mongodb-compass"], src: mongodbCompassIcon },
  { key: "pycharm", name: "PyCharm", aliases: ["pycharm", "pycharm.sh", "pycharm-community", "pycharm-communi", "pycharm-professional", "pycharm-profess"], src: pycharmIcon },
  { key: "webstorm", name: "WebStorm", aliases: ["webstorm", "webstorm.sh"], src: webstormIcon },
  { key: "eclipse", name: "Eclipse IDE", aliases: ["eclipse"], src: eclipseIcon },
  { key: "netbeans", name: "Apache NetBeans", aliases: ["netbeans"], src: netbeansIcon },
  { key: "android-studio", name: "Android Studio", aliases: ["android-studio", "studio.sh"], src: androidStudioIcon },
  { key: "virtualbox", name: "VirtualBox", aliases: ["virtualbox", "virtualboxvm", "vboxheadless", "vboxsvc"], src: virtualboxIcon },
  { key: "qemu", name: "QEMU", aliases: ["qemu-system-x86_64", "qemu-system-x86", "qemu-system-i386", "qemu-system-i38", "qemu-system-aarch64", "qemu-system-aar", "qemu-kvm"], src: qemuIcon, darkClassName: "dark:invert" },
  { key: "jenkins", name: "Jenkins", aliases: ["jenkins"], src: jenkinsIcon },
  { key: "kubernetes", name: "Kubernetes / kubectl", aliases: ["kubectl", "kubelet", "kube-apiserver", "kube-proxy", "kube-scheduler", "kube-controller-manager", "kube-controller"], src: kubernetesIcon },
  { key: "ollama", name: "Ollama", aliases: ["ollama", "ollama_llama_server", "ollama_llama_se"], src: ollamaIcon, darkClassName: "dark:invert" },
  { key: "opencode", name: "OpenCode", aliases: ["opencode"], src: opencodeIcon, darkClassName: "dark:invert" },
  { key: "chatgpt", name: "ChatGPT Desktop", aliases: ["chatgpt", "chatgpt-desktop"], src: chatgptIcon, darkClassName: "dark:invert" },
  { key: "zed", name: "Zed Editor", aliases: ["zed"], src: zedIcon },
];

const appByAlias: ReadonlyMap<string, ProcessAppDefinition> = new Map(
  processApps.flatMap((app) => app.aliases.map((alias) => [alias, app] as const)),
);

export function resolveProcessApp(name: string): ProcessAppDefinition | undefined {
  return appByAlias.get(name.trim().toLowerCase());
}

export type ProcessIconResolution =
  | { kind: "brand"; src: string; key: string; darkClassName?: string }
  | { kind: "fallback"; icon: LucideIcon };

export function resolveProcessIcon(name: string): ProcessIconResolution {
  const app = resolveProcessApp(name);
  if (app?.src) {
    return {
      kind: "brand",
      src: app.src,
      key: app.key,
      ...(app.darkClassName ? { darkClassName: app.darkClassName } : {}),
    };
  }
  return { kind: "fallback", icon: AppWindow };
}

/** Convenience fallback exported for callers that want the generic icon. */
export const fallbackProcessIcon: LucideIcon = AppWindow;

type ProcessIconProps = {
  name: string;
  className?: string;
  "data-testid"?: string;
};

/** React component rendering the resolved icon at the requested size. */
export function ProcessIcon({
  name,
  className,
  "data-testid": testId,
}: ProcessIconProps): React.ReactElement {
  const resolved = resolveProcessIcon(name);
  const resolvedSrc = resolved.kind === "brand" ? resolved.src : null;
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  // A new source is a fresh attempt: forget the previous failure so switching
  // back to a brand retries once instead of staying on the fallback.
  useEffect(() => {
    setFailedSrc(null);
  }, [resolvedSrc]);

  if (resolved.kind === "brand" && failedSrc !== resolved.src) {
    const imageClassName =
      [className, resolved.darkClassName, "object-contain"].filter(Boolean).join(" ") || undefined;
    return React.createElement("img", {
      src: resolved.src,
      alt: "",
      "aria-hidden": "true",
      className: imageClassName,
      width: 16,
      height: 16,
      "data-testid": testId,
      onError: () => setFailedSrc(resolved.src),
    } as React.ImgHTMLAttributes<HTMLImageElement>);
  }

  const Icon = resolved.kind === "fallback" ? resolved.icon : AppWindow;
  return React.createElement(Icon, {
    "aria-hidden": "true",
    className,
    size: 16,
    "data-testid": testId,
  } as React.ComponentProps<typeof AppWindow>);
}
