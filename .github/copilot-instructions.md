# Copilot Instructions

## Project overview
- This is an agricultural procurement app.
- The Python backend lives in `sih-backend`.
- The frontend is a React + TypeScript app in `sih-mobile-frontend`.
- Keycloak is used for authentication and user management via OAuth/OIDC.
- The Keycloak setup is in `keycloak/docker-compose.yml`.

## Backend guidance
- Treat the Python backend as the source of business logic and APIs.
- Keep code clean, modular, and maintainable.
- Prefer secure, well-structured REST API patterns.
- Validate inputs and keep auth-related access checks in place.
- Do not introduce frontend logic into the backend.

## Frontend guidance
- The frontend is mobile-first and should prioritize responsive layouts for phones.
- Use React + TypeScript patterns and keep components simple and reusable.
- Design for touch-friendly interactions, small screens, and clear mobile navigation.
- Avoid desktop-heavy layouts or assumptions.
- Keep UI consistent with a modern procurement dashboard/mobile app style.

## Authentication guidance
- Keycloak provides user management and OAuth authentication.
- Users are created manually after starting the Keycloak service.
- The frontend should authenticate using Keycloak APIs and OIDC flows.
- Do not build a custom auth system; integrate with Keycloak.

## Project workflow
- Backend changes should be made in `sih-backend`.
- Frontend changes should be made in `sih-mobile-frontend`.
- Use the Keycloak Docker setup to bring up the auth service before local development.
- Keep changes focused and avoid unrelated project-wide refactors.
