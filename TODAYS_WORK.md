
# Our work for TODAY

- Our goal today is to get the amplifier-app-api fixedup and deployed to production.
- I am going to give you a set of tasks to do in Phases. So phase 1,2,3, etc.
- Finish all work in the current phase before moving onto the next.
- Start by committing all our changes. That way we have a clean working environment.


## Phase 1 - Endpoint testing
- Spin up the service locally - localhost:8765
- Test all endpoints on the /docs page.
- Many of them need to be tested in a certain order. We need applications and configs before we can start a session for example.
- If any of the endpoints fail, go figure out why and fix it.
- If/when you make changes, be careful that you don't break any other endpoints by accident
- See if there are any places where you can made assumptions about how to proceed. For example, if a version isn't provided, then just choose 1.0.0. IF an orchestrator isn't provided, then jsut use loop-basic, etc.
- Once this is complete, then move onto the next. You should be able to say "I ran every single endpoint listed on the SWAGGER UI page, and they all succeeded.
- Commit all these changes to the "revision/version-0.3.0-major-updates" branch


## Phase 2 - example configs
- For all of these endpoints, make sure any config/examples we show to the user is correct. Including whether the fields are required or not. For example, the sample json we show for a config should match what the service expects to get.
- Make sure that Swagger UI page is perfectly accurate.
- You should be able to say  "I looked at every example or config on the SWAGGER UI and they match what the service expects, perfectly"
- Commit all these changes to the "revision/version-0.3.0-major-updates" branch

## Phase 3 - test suite update
- We hve a very robust test suite for this project, and I want to maintain that coverage.
- Look through ALL of our test cases for this project. Update any that need to be updated, remove any that are no longer valuable, and add any we are missing.
- Double check yourself here. If there's an opportunity to add a test, do it.
- Then run ALL of the tests. IF any break, fix them. Don't assume a certain % of success is ok. They must ALL pass.
- Then look at your E2E tests. Same principles here. Update any that need to be updated, remove any that are no longer needed, and add any that need to be added.
- Then run all of your E2E tests against the locally running service at https://localhost:8765
- This is a big one. You should be able to say "I ran ALL tests (there are hundreds of them) and ALL E2E test, and they all completed successfully"
- Commit all these changes to the "revision/version-0.3.0-major-updates" branch

## Phase 4 - Documentation
- Afrer all of this time, our documentation is going to be out of date.
- Look through all of our documenation in all folders and understand it deeply.
- Update any documentation that needs to be updated so it reflects our service. Remove any documenation that is obsolete or no longer needed. Add any documentation that is need.
- You should be able to say "Our documentation is amazing. It broad, accurate, and detailed."
- Commit all these changes to the "revision/version-0.3.0-major-updates" branch

## Phase 4 - Final work
- Run a clean build with no caching and spin it up locally.
- Re run all the tests to make sure something didn't break
- Commit any changes you had to make to the "revision/version-0.3.0-major-updates" branch
- Create a PR for that branch.
