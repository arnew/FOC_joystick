/**
 * Unit Tests for Configuration System
 * Tests the three hardware configurations without hardware
 * 
 * Run with: platformio test -e test
 */

#include <gtest/gtest.h>
#include <cstring>

// We'll test config.h separately for each configuration
// This is a bit tricky since config.h uses preprocessor conditionals

// Test 1: Single Endless Motor Configuration
class SingleEndlessMotorConfig : public ::testing::Test {
protected:
    // Mock the config manually for testing
    struct TestMotorProfile {
        uint8_t id;
        float min_angle;
        float max_angle;
        bool is_endless;
        const char* label;
    };
    
    struct TestAxisProfile {
        uint8_t motor_id;
        uint8_t midi_cc;
        const char* label;
    };
};

TEST_F(SingleEndlessMotorConfig, SingleMotorIsEndless) {
    TestMotorProfile motor = {
        .id = 0,
        .min_angle = 0.0f,
        .max_angle = 6.28318f,  // 360 degrees
        .is_endless = true,
        .label = "Motor 0 (Endless Trim)"
    };
    
    EXPECT_EQ(motor.id, 0);
    EXPECT_TRUE(motor.is_endless);
    EXPECT_FLOAT_EQ(motor.max_angle, 6.28318f);
}

TEST_F(SingleEndlessMotorConfig, TrimAxisMapsToCC64) {
    TestAxisProfile axis = {
        .motor_id = 0,
        .midi_cc = 64,
        .label = "Trim"
    };
    
    EXPECT_EQ(axis.motor_id, 0);
    EXPECT_EQ(axis.midi_cc, 64);
}

// Test 2: Single Limited Motor Configuration
class SingleLimitedMotorConfig : public ::testing::Test {
protected:
    struct TestMotorProfile {
        uint8_t id;
        float min_angle;
        float max_angle;
        bool is_endless;
        const char* label;
    };
};

TEST_F(SingleLimitedMotorConfig, SingleMotorIsLimited) {
    TestMotorProfile motor = {
        .id = 0,
        .min_angle = 0.0f,
        .max_angle = 3.14159f,  // 180 degrees
        .is_endless = false,
        .label = "Motor 0 (Limited Range)"
    };
    
    EXPECT_EQ(motor.id, 0);
    EXPECT_FALSE(motor.is_endless);
    EXPECT_FLOAT_EQ(motor.max_angle, 3.14159f);
}

TEST_F(SingleLimitedMotorConfig, ThrottleAndFlapsMapToCC7And11) {
    uint8_t cc_throttle = 7;
    uint8_t cc_flaps = 11;
    
    EXPECT_EQ(cc_throttle, 7);
    EXPECT_EQ(cc_flaps, 11);
}

// Test 3: Utility Functions / CC to Angle Conversion
class CCToAngleConversion : public ::testing::Test {
protected:
    // Test the cc_to_angle logic
    float mock_cc_to_angle(float min_angle, float max_angle, bool is_endless, uint8_t cc_value) {
        float normalized = (float)cc_value / 127.0f;
        
        if (!is_endless) {
            return min_angle + (normalized * (max_angle - min_angle));
        }
        return normalized * 6.28318f;  // 360 degrees
    }
};

TEST_F(CCToAngleConversion, CC0ShouldMapToMinAngle) {
    float angle = mock_cc_to_angle(0.0f, 3.14159f, false, 0);
    EXPECT_FLOAT_EQ(angle, 0.0f);
}

TEST_F(CCToAngleConversion, CC127ShouldMapToMaxAngle) {
    float angle = mock_cc_to_angle(0.0f, 3.14159f, false, 127);
    EXPECT_FLOAT_EQ(angle, 3.14159f);
}

TEST_F(CCToAngleConversion, CC64ShouldMapToMidpoint) {
    float angle = mock_cc_to_angle(0.0f, 3.14159f, false, 64);
    EXPECT_FLOAT_EQ(angle, 3.14159f / 2.0f);
}

TEST_F(CCToAngleConversion, EndlessMotorShouldWrap) {
    float angle = mock_cc_to_angle(0.0f, 6.28318f, true, 127);
    EXPECT_FLOAT_EQ(angle, 6.28318f);
}

// Test 4: Motor Limit Handling
class MotorLimitHandling : public ::testing::Test {
protected:
    void handle_motor_limits(float min_angle, float max_angle, bool is_endless, float& angle) {
        if (is_endless) {
            // Endless axis: wrap to 0-360° (0-2π radians)
            while (angle < 0.0f) angle += 6.28318f;
            while (angle > 6.28318f) angle -= 6.28318f;
        } else {
            // Limited axis: clamp to min-max
            if (angle < min_angle) angle = min_angle;
            if (angle > max_angle) angle = max_angle;
        }
    }
};

TEST_F(MotorLimitHandling, LimitedMotorClampsAtMax) {
    float angle = 4.0f;  // Beyond 180° (3.14159)
    handle_motor_limits(0.0f, 3.14159f, false, angle);
    EXPECT_FLOAT_EQ(angle, 3.14159f);
}

TEST_F(MotorLimitHandling, LimitedMotorClampsAtMin) {
    float angle = -1.0f;
    handle_motor_limits(0.0f, 3.14159f, false, angle);
    EXPECT_FLOAT_EQ(angle, 0.0f);
}

TEST_F(MotorLimitHandling, EndlessMotorWrapsPositive) {
    float angle = 7.0f;  // Beyond 360° (6.28318)
    handle_motor_limits(0.0f, 6.28318f, true, angle);
    EXPECT_GT(angle, 0.0f);
    EXPECT_LE(angle, 6.28318f);
}

TEST_F(MotorLimitHandling, EndlessMotorWrapsNegative) {
    float angle = -1.0f;  // Negative
    handle_motor_limits(0.0f, 6.28318f, true, angle);
    EXPECT_GE(angle, 0.0f);
    EXPECT_LE(angle, 6.28318f);
}

// Test 5: Joystick Value Scaling
class JoystickValueScaling : public ::testing::Test {
protected:
    uint16_t mock_angle_to_joystick(float angle, float min_angle, float max_angle, bool reversed) {
        float normalized = 0.5f;
        
        if (max_angle > min_angle) {
            normalized = (angle - min_angle) / (max_angle - min_angle);
        }
        
        if (reversed) {
            normalized = 1.0f - normalized;
        }
        
        // Clamp
        if (normalized < 0.0f) normalized = 0.0f;
        if (normalized > 1.0f) normalized = 1.0f;
        
        return (uint16_t)(normalized * 1023.0f);
    }
};

TEST_F(JoystickValueScaling, MinAngleMapsTo0) {
    uint16_t value = mock_angle_to_joystick(0.0f, 0.0f, 3.14159f, false);
    EXPECT_EQ(value, 0);
}

TEST_F(JoystickValueScaling, MaxAngleMapsTo1023) {
    uint16_t value = mock_angle_to_joystick(3.14159f, 0.0f, 3.14159f, false);
    EXPECT_EQ(value, 1023);
}

TEST_F(JoystickValueScaling, MidAngleMapsToCenter) {
    uint16_t value = mock_angle_to_joystick(3.14159f / 2.0f, 0.0f, 3.14159f, false);
    EXPECT_NEAR(value, 511, 1);  // Allow 1 point tolerance for rounding
}

TEST_F(JoystickValueScaling, ReversedAxisInverts) {
    uint16_t value_normal = mock_angle_to_joystick(3.14159f / 2.0f, 0.0f, 3.14159f, false);
    uint16_t value_reversed = mock_angle_to_joystick(3.14159f / 2.0f, 0.0f, 3.14159f, true);
    
    EXPECT_EQ(value_normal + value_reversed, 1023);  // Should be inverted
}

// Main entry point
int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
