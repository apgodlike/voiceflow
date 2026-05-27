package com.voiceflow.app

import com.voiceflow.app.core.Cleaner
import org.junit.Assert.assertEquals
import org.junit.Test

class CleanerTest {
    @Test fun stripsSimpleFillers() {
        assertEquals("Hello world.", Cleaner.clean("um so basically hello world"))
    }

    @Test fun stripsTrailingRight() {
        assertEquals("This works.", Cleaner.clean("this works right"))
    }

    @Test fun stripsBeLikeButKeepsVerb() {
        assertEquals("I was going.", Cleaner.clean("I was like going"))
    }

    @Test fun keepsBareLike() {
        assertEquals("I like coffee.", Cleaner.clean("I like coffee"))
    }

    @Test fun capitalizesAndAddsPeriod() {
        assertEquals("Hello.", Cleaner.clean("hello"))
    }

    @Test fun keepsExistingTerminalPunctuation() {
        assertEquals("Done!", Cleaner.clean("done!"))
    }

    @Test fun emptyStaysEmpty() {
        assertEquals("", Cleaner.clean(""))
    }
}
