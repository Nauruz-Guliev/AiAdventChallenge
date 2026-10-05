# Kotlin Multiplatform samples

<show-structure for="none"/>

This is a curated list of projects that aims to show robust and unique applications of Kotlin Multiplatform.

> We are not currently accepting contributions to this page.
> To feature your project as a sample of Kotlin Multiplatform, use the [kotlin-multiplatform-sample](https://github.com/topics/kotlin-multiplatform-sample) topic on GitHub.
> See the [GitHub documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics#adding-topics-to-your-repository)
to learn how to feature your project in topics.
>

Some projects share almost all their code using Compose Multiplatform for the user interface.
Others use native code for the user interface and share, for example, only the data model and algorithms.
To create your own brand new Kotlin Multiplatform application, we recommend using the [web wizard](https://kmp.jetbrains.com).

You can find even more sample projects on GitHub via the [kotlin-multiplatform-sample](https://github.com/topics/kotlin-multiplatform-sample) topic. 
To explore the ecosystem as a whole, check out the [kotlin-multiplatform](https://github.com/topics/kotlin-multiplatform) topic.

### JetBrains official samples

    <tr>
        <td>Name</td>
        <td>Description</td>
        <td>What's shared?</td>
        <td>Noteworthy libraries</td>
        <td>User interface</td>
    </tr>
    <tr>
        <td>
            <strong>Official KotlinConf application</strong>
        </td>
        <td>A companion application for KotlinConf.
            The client application for Android, iOS, desktop, and web is built with shared UI using Compose Multiplatform.
            The backend application is powered by the Ktor server-side framework
            and the Exposed database library.
        </td>
        <td>
            <list>
                UI
                Model
                Networking
                Data storage
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-serialization</code>
                <code>kotlinx-datetime</code>
                <code>kotlinx-coroutines</code>
                <code>ktor-client</code>
                <code>ktor-server</code>
                <code>multiplatform-settings</code>
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android
                Compose Multiplatform on iOS, desktop, and web
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Image Viewer</strong>
        </td>
        <td>An application for capturing, viewing, and storing pictures. Includes support for maps. Uses Compose
            Multiplatform for the UI. Introduced at KotlinConf 2023.
        </td>
        <td>
            <list>
                UI
                Model
                Networking
                Animation
                Data storage
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-serialization</code>
                <code>kotlinx-datetime</code>
                <code>kotlinx-coroutines</code>
                <code>play-services-maps</code>
                <code>play-services-locations</code>
                <code>android-maps-compose</code>
                <code>accompanist-permissions</code>
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android
                Compose Multiplatform on iOS, desktop, and web
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Chat</strong>
        </td>
        <td>A demonstration of how to embed Compose Multiplatform components within a SwiftUI interface. The use case is online messaging.
        </td>
        <td>
            <list>
                UI
                Model
                Networking
            </list>
        </td>
        <td/>
        <td>
            <list>
                Jetpack Compose on Android
                Compose Multiplatform on iOS, desktop, and web
                SwiftUI on iOS
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Jetcaster Multiplatform</strong>
        </td>
        <td>The Compose sample Jetcaster app
            made multiplatform, with added iOS and desktop targets added to the original Android version.
            The UI is migrated to use Compose Multiplatform, and several libraries are replaced with their multiplatform versions
            or alternatives.
            The migration reasoning and process are described
            in the Jetcaster migration tutorial.
        </td>
        <td>
            <list>
                Model
                Networking
                UI
                Data storage
            </list>
        </td>
        <td>
            <list>
                <code>coil</code>
                <code>koin</code>
                <code>kotlinx-coroutines</code>
                <code>kotlinx-datetime</code>
                <code>kotlin-test</code>
                <code>ktor-client</code>
                Room
            </list>
        </td>
        <td>
            <list>
                Compose Multiplatform on Android, iOS, and desktop
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>KMM RSS Reader</strong>
        </td>
        <td>A sample application for consuming RSS feeds designed to show how Kotlin Multiplatform can be used in
            production. The UI is implemented natively, but there is an experimental branch showing how Compose
            Multiplatform could be used on iOS and desktop. Networking is accomplished using the
            Ktor HTTP Client, while XML parsing is
            implemented natively. The Redux architecture is used for sharing UI State.
        </td>
        <td>
            <list>
                Model
                Networking
                UI state
                Data storage
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-serialization</code>
                <code>kotlinx-coroutines</code>
                <code>ktor-client</code>
                <code>voyager</code>
                <code>coil</code>
                <code>multiplatform-settings</code>
                <code>napier</code>
                SQLDelight
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android
                Compose Multiplatform on iOS and desktop (on experimental branch)
                SwiftUI on iOS
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Kotlin Multiplatform Sample</strong>
        </td>
        <td>A simple calculator application. Showing how to integrate Kotlin and native code using expected and actual declarations.
        </td>
        <td>Algorithms</td>
        <td/>
        <td>
            <list>
                Jetpack Compose on Android
                SwiftUI
            </list>
        </td>
    </tr>

### Recommended samples

    <tr>
        <td>Name</td>
        <td>Description</td>
        <td>What's shared?</td>
        <td>Noteworthy libraries</td>
        <td>User interface</td>
    </tr>
    <tr>
        <td>
            <strong>Confetti</strong>
        </td>
        <td>A showcase of many different aspects of Kotlin Multiplatform and Compose Multiplatform. The use case is an
            application for fetching and displaying information about conference schedules. Includes support for the
            Wear and Auto platforms. Uses GraphQL for client-server communications. The architecture is discussed
            in-depth at KotlinConf 2023.
        </td>
        <td>
            <list>
                UI
                Model
                Networking
                Data storage
                Navigation
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-serialization</code>
                <code>kotlinx-datetime</code>
                <code>kotlinx-coroutines</code>
                <code>decompose</code>
                <code>koin</code>
                <code>jsonpathkt-kotlinx</code>
                <code>horologist</code>
                <code>google-cloud</code>
                <code>firebase</code>
                <code>bare-graphql</code>
                <code>apollo</code>
                <code>accompanist</code>
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android, Auto, and Wear
                Compose Multiplatform on iOS, desktop, and web
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>People In Space</strong>
        </td>
        <td>A showcase of the many different platforms on which Kotlin Multiplatform can run. The use case is to show
            the number of people currently in space and the position of the International Space Station.
        </td>
        <td>
            <list>
                Model
                Networking
                Data storage
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-serialization</code>
                <code>kotlinx-coroutines</code>
                <code>kotlinx-datetime</code>
                <code>ktor-client</code>
                <code>koin</code>
                <code>multiplatform-settings</code>
                SQLDelight
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android and Wear OS
                Compose Multiplatform on iOS, desktop, and web
                SwiftUI on iOS and macOS
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Sessionize / Droidcon</strong>
        </td>
        <td>An application for viewing the agenda at Droidcon events using the Sessionize API. Can be customized for use
            with any event that stores talks in Sessionize. Integrates with Firebase and so requires a Firebase account to run.
        </td>
        <td>
            <list>
                UI
                Model
                Networking
                Data storage
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-coroutines</code>
                <code>kotlinx-datetime</code>
                <code>ktor-client</code>
                <code>koin</code>
                <code>multiplatform-settings</code>
                <code>firebase</code>
                <code>kermit</code>
                <code>accompanist</code>
                <code>hyperdrive-multiplatformx</code>
                SQLDelight
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android
                Compose Multiplatform on iOS
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>KaMPKit</strong>
        </td>
        <td>A collection of code and tools for Kotlin Multiplatform development. Designed to showcase libraries,
            architectural choices, and best practices when building Kotlin Multiplatform applications. The use case is
            downloading and displaying information about dog breeds. Introduced in this video tutorial.
        </td>
        <td>
            <list>
                Model
                Networking
                ViewModel
                Data storage
            </list>
        </td>
        <td>
            <list>
                <code>ktor-client</code>
                <code>koin</code>
                <code>multiplatform-settings</code>
                <code>kermit</code>
                SQLDelight
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android
                SwiftUI on iOS
            </list>
        </td>
    </tr>

### Other community samples

    <tr>
        <td>Name</td>
        <td>Description</td>
        <td>What's shared?</td>
        <td>Noteworthy libraries</td>
        <td>User interface</td>
    </tr>
    <tr>
        <td>
            <strong>NYTimes KMP</strong>
        </td>
        <td>A Compose Multiplatform based version of the New York Times application. Allows the user to browse and read
            articles. Note that to build and run the application, you will need an API key from the New York Times.
        </td>
        <td>
            <list>
                UI
                Model
                Networking
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-serialization</code>
                <code>kotlinx-datetime</code>
                <code>kotlinx-coroutines</code>
                <code>ktor-client</code>
                <code>molecule</code>
                <code>decompose</code>
                <code>horologist</code>
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android and Wear
                Compose Multiplatform on iOS, desktop, and web
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Focus Bloom</strong>
        </td>
        <td>A productivity and time management application. Allows users to schedule tasks and provides feedback on their accomplishments.
        </td>
        <td>
            <list>
                UI
                Model
                Animation
                Data storage
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx.serialization</code>
                <code>kotlinx.coroutines</code>
                <code>kotlinx.datetime</code>
                <code>koin</code>
                <code>navigation-compose</code>
                <code>multiplatform-settings</code>
                SQLDelight
            </list>
        </td>
        <td>
            <list>
                Compose Multiplatform on Android, iOS, and desktop
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Recipe App</strong>
        </td>
        <td>A demonstration application for viewing recipes. Showcases the use of animations.</td>
        <td>
            <list>
                UI
                Model
                Data storage
            </list>
        </td>
        <td><code>kotlinx-coroutines</code></td>
        <td>
            <list>
                Jetpack Compose on Android
                Compose Multiplatform on iOS, desktop, and web
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>D-KMP-sample</strong>
        </td>
        <td>A sample application for the 
            Declarative UIs with Kotlin MultiPlatform architecture. The use case is retrieving and displaying
            vaccination statistics for different countries.
        </td>
        <td>
            <list>
                Networking
                Data storage
                ViewModel
                Navigation
            </list>
        </td>
        <td>
            <list>
                <code>ktor-client</code>
                <code>multiplatform-settings</code>
                SQLDelight
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android
                SwiftUI on iOS
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Notflix</strong>
        </td>
        <td>An application that consumes data from The Movie Database to
            display current trending, upcoming, and popular movies and TV shows. Requires that you create an API key
            with The Movie Database.
        </td>
        <td>
            <list>
                Model
                Networking
                Caching
                ViewModel
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-coroutines</code>
                <code>kotlinx-serialization</code>
                <code>kotlinx-datetime</code>
                <code>ktor-client</code>
                <code>multiplatform-settings</code>
                <code>napier</code>
            </list>
        </td>
        <td>
            <list>
                Jetpack Compose on Android
                SwiftUI on iOS
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Twine - RSS Reader</strong>
        </td>
        <td>Twine is a multiplatform RSS reader app built using Kotlin and Compose Multiplatform. It features a nice
            user interface and experience to browse through the feeds and supports Material 3 content-based dynamic
            theming.
        </td>
        <td>
            <list>
                Model
                Networking
                Data Storage
                UI
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-coroutines</code>
                <code>kotlinx-serialization</code>
                <code>kotlinx-datetime</code>
                <code>ktor-client</code>
                <code>napier</code>
                <code>decompose</code>
            </list>
        </td>
        <td>
            <list>
                Compose Multiplatform on Android and iOS
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Shopping By KMP</strong>
        </td>
        <td>A cross-platform application that is built using Jetpack Compose Multiplatform, a declarative framework for
            sharing UIs across multiple platforms with Kotlin. The application allows users to browse, search, and
            purchase products from a shopping catalog on Android, iOS, web, desktop, Android Automotive, and Android TV.
        </td>
        <td>
            <list>
                Model
                Networking
                Data Storage
                UI
                ViewModel
                Animation
                Navigation
                UI state
                Use Case
                Unit Test
                UI Test
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-coroutines</code>
                <code>kotlinx-serialization</code>
                <code>kotlinx-datetime</code>
                <code>ktor-client</code>
                <code>datastore</code>
                <code>koin</code>
                <code>google-map</code>
                <code>navigation-compose</code>
                <code>coil</code>
                <code>kotest</code>
            </list>
        </td>
        <td>
            <list>
                Compose Multiplatform on Android, iOS, web, desktop, automotive, and Android TV
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Music App KMP</strong>
        </td>
        <td>An application showcasing how to interact with native APIs like MediaPlayer on different platforms. It uses
            Spotify API to fetch data.
        </td>
        <td>
            <list>
                Model
                Networking
                UI
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-coroutines</code>
                <code>kotlinx-serialization</code>
                <code>ktor-client</code>
                <code>decompose</code>
            </list>
        </td>
        <td>
            <list>
                Compose Multiplatform on Android, iOS, desktop, and web
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <strong>Rijksmuseum</strong>
        </td>
        <td>Rijksmuseum is a multimodular Kotlin and Compose Multiplatform app that offers an immersive way to explore
            the art collection of the renowned Rijksmuseum in Amsterdam. It utilizes the Rijksmuseum API to fetch and
            display detailed information about various artworks, including images and descriptions.
        </td>
        <td>
            <list>
                UI
                Model
                Networking
                Navigation
                ViewModel
            </list>
        </td>
        <td>
            <list>
                <code>kotlinx-coroutines</code>
                <code>kotlinx-serialization</code>
                <code>ktor-client</code>
                <code>koin</code>
                <code>navigation-compose</code>
                <code>Coil</code>
                <code>Jetpack ViewModel</code>
            </list>
        </td>
        <td>
            <list>
                Compose Multiplatform on Android, iOS, desktop, and web
            </list>
        </td>
    </tr>
