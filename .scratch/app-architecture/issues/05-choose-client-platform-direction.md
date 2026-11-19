# Choose the web and native client platform direction

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 01, 04

## Question

What does native mean for this product, and which client-platform approach best preserves the desired code sharing across web, iPhone, and Android without imposing unjustified initial overhead? Decide the near-term platform sequence, acceptable platform-specific code, and the repository/package direction using the research and quality targets. Identify any prototype or additional research needed rather than assuming that one repository guarantees shared implementations.

## Comments

### Human discussion — 2026-11-06 (Pacific/Honolulu)

- The user accepted native UI controls as the mobile direction: the app should feel native rather than like a wrapped website.
- The user accepted separate web and mobile screens/navigation, with shared application logic, domain rules, and API contracts where practical.
- Prefer established approaches and existing libraries; avoid reimplementing existing solutions or creating a custom cross-platform framework.
- The framework and repository/package direction remain under discussion. Web-first delivery was already settled in [Set the architecture's quality targets and decision priorities](04-architecture-quality-targets.md).
- The agent proposed React DOM/TypeScript for web with a later Expo/React Native mobile app and shared workspace packages. The user has not accepted this choice; they requested an explanation of React Native for Web, Expo's additions to React Native, and the overhead of adopting Expo from the start.
- After discussing those distinctions and costs, the user explicitly chose Expo and React Native for Web from the start. This settles the framework direction and supersedes the earlier proposal to start with a separate React DOM web app.

## Answer

Resolved through human discussion on 2026-11-06 (Pacific/Honolulu).

### Choices and rationale

- **Expo and React Native for Web from the start.** Use the React Native component model, rendered through React Native for Web in the browser, within Expo's tooling. TypeScript is the starting client language. This creates an opportunity to share presentation as well as application logic with later iOS and Android clients. The selected direction replaces the separate-React-DOM-web-first proposal; native delivery still follows web delivery.
- **Native mobile experience.** Future iOS and Android apps use React Native's native platform views, with platform-appropriate interactions. Installation and camera access alone do not satisfy the user's native requirement. Native feel also requires deliberate navigation, layout, accessibility, and device testing; choosing a renderer does not establish those qualities by itself.
- **Practical sharing rather than identical screens.** Share compatible UI, client application logic, domain rules, and API contracts where useful. Allow web-, iOS-, and Android-specific components, screens, navigation, and capability adapters. Ordinary React DOM components remain available for genuinely web-specific needs, but they do not become shared native presentation automatically. No sharing percentage or universal-screen requirement is adopted.
- **One repository, a shared client codebase, and ordinary package boundaries.** Keep the Python backend and Expo client in the same repository, with web and future mobile targets supported by the client direction. Keep reusable client logic independent of browser or native APIs. Use normal modules and workspace packages when a concrete sharing boundary calls for them; exact directories and package tooling belong to the frontend-boundaries decision. A separate web application and separate mobile application are not prerequisites for this direction.
- **Established framework and libraries.** Use Expo and compatible existing libraries for common navigation and device capabilities, following the user's preference against reimplementing existing solutions or building a custom cross-platform framework. Expo supplies development/build tools, capability libraries, and native-project configuration support around React Native. Expo's hosted build/update services are optional; selecting the framework does not select hosted services or replace the proposed Python backend.

The trade-off is accepting React Native's component/styling conventions, cross-platform library checks, and Expo's coordinated dependency upgrades earlier, in exchange for a common development approach and more potential UI reuse. Web-first delivery does not mean treating web-only dependencies as portable. Conversely, preserving future mobile support does not require delivering or signing native apps now.

### What must be fixed now

- Use Expo with React Native for Web as the client-platform direction when planning frontend boundaries and contracts.
- Preserve platform-independent logic and explicit browser/native integration boundaries; do not put browser-only dependencies into code intended to be shared.
- Allow platform-specific presentation instead of inventing a compatibility framework or forcing every screen to be identical.
- Keep the agreed web-first, online-first delivery sequence and backend/client separation. This decision does not resolve transport, authentication, imports, or deployment.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary or starting assumption | Revisit trigger / owning ticket |
| --- | --- | --- |
| Exact shared modules/packages, state libraries, UI libraries, navigation, and directory layout | Expo/React Native for Web direction; compatible shared code plus platform-specific implementations | Before establishing frontend dependencies; [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md) |
| Browser versus native credentials and session storage | Common ownership/session concepts with platform-specific storage and lifecycle handling | Before defining session contracts; [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md) |
| Photo/camera permissions, input handling, and interruption recovery | Use established capability libraries behind platform boundaries; temporary extraction inputs remain subject to the agreed retention rules | When tracing imports and frontend lifecycles; [Define import review and background-work lifecycles](11-imports-and-background-work.md) and [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md) |
| Native build/signing/release setup and detailed native acceptance checks | Deliver web first; native delivery remains outside this map | When native delivery is scheduled, or earlier if a required capability cannot be supported by the selected ecosystem |
| Expo hosted services and quantitative performance/bundle costs | Hosted services are optional; no extra service commitment or measured overhead claim is made here | When choosing deployment/build infrastructure or when measurements show a relevant budget or responsiveness problem; [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md) |

### Cost of reversal and evidence needs

Changing the rendering family after substantial UI work would mean replacing components, styling, navigation, and integrations; that is the costly choice made here. Platform-independent TypeScript logic and backend contracts should survive more readily. Exact package splits and individual libraries are more replaceable while dependencies remain contained. Moving away from Expo tooling may require taking over native-project and build configuration even if React Native presentation is retained.

No additional blocking research or prototype is identified for this direction: it uses the documented framework path rather than a novel integration. Actual mobile reuse, native feel, photo behavior, accessibility, and performance remain to be validated when those workflows are built. A concrete capability gap or unacceptable measured behavior should trigger a focused investigation or prototype rather than an assumed framework guarantee.

Supporting evidence: [Research approaches to sharing web, iOS, and Android code](01-research-shared-mobile-approaches.md), [React Native for Web introduction](https://necolas.github.io/react-native-web/docs/), [React Native framework guidance](https://reactnative.dev/docs/environment-setup), [Expo web support](https://docs.expo.dev/workflow/web/), [Expo development overview](https://docs.expo.dev/workflow/overview/), and [Expo upgrade workflow](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/). These establish capabilities and maintenance obligations, not a project-specific reuse or performance result.
