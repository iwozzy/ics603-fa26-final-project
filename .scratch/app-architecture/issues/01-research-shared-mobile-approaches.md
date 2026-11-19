# Research approaches to sharing web, iOS, and Android code

Type: research
Labels: wayfinder:research
Status: resolved
Assignee: Codex architecture mobile research
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)

## Question

Which currently supported approaches can provide web and native iOS/Android clients with substantial code sharing in one repository? Compare a focused set of plausible options (including shared React/React Native approaches, Flutter, and web-plus-native-wrapper approaches), citing primary sources. Distinguish native UI, native capabilities, and a wrapped web UI; quantify sharing only where evidence supports it. Assess frontend ports and adapters, camera/photo imports, accessibility, navigation, deployment/build tooling, and incremental adoption. Identify what the human must decide about “native” and the cost of changing frameworks later. Provide evidence and trade-offs, not a framework selection or prototype.

## Answer

Primary-source research compares three rendering families and four project arrangements: universal Expo/React Native, separate React DOM and React Native clients, Flutter, and a web client packaged with Capacitor. All have supported photo/camera paths, but platform permissions, lifecycle recovery, navigation, accessibility, and release builds remain real work. The sources do not justify a project-specific code-sharing percentage. The human must define whether “native” requires OS views, installation/native capabilities, or a particular interaction standard before choosing a rendering family. Frontend use cases and small platform adapters can preserve logic, but changing UI frameworks still replaces substantial presentation code; a Dart transition also changes the client language. No framework was selected and no prototype was built.

Committed report: [Sharing web, iOS, and Android clients](https://github.com/iwozzy/ics603-fa26-final-project/blob/bdd2ec43de458075bde0b3fb3d3f93515dd2acc3/.scratch/app-architecture/research/shared-mobile-approaches.md).

Exact context pointer: branch `research/app-architecture-mobile`, commit `bdd2ec43de458075bde0b3fb3d3f93515dd2acc3`, path `.scratch/app-architecture/research/shared-mobile-approaches.md`. The branch was successfully pushed to `origin`; no PR or merge was created. Local worktree report: `/private/tmp/ics603-app-architecture-mobile/.scratch/app-architecture/research/shared-mobile-approaches.md`.
