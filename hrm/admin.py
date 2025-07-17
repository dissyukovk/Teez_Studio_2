# hrm/admin.py

from django.contrib import admin
from .models import (
    Department, Position, Shift, ShiftAssignment, 
    LeaveType, LeaveRequest, FactualTimeLog,
    HRMStatus, Holiday, LeaveRequestStatus 
)

admin.site.register(Department)
admin.site.register(Position)
admin.site.register(Shift)
admin.site.register(ShiftAssignment)
admin.site.register(LeaveType)
admin.site.register(LeaveRequest)
admin.site.register(FactualTimeLog)
admin.site.register(HRMStatus)
admin.site.register(Holiday)
admin.site.register(LeaveRequestStatus)
