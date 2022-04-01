import simulator.models.customer.customer_repository
from common import geoutils, mesh
from simulator.settings import FLAGS

class VehicleBehavior(object):
    available = True

    def step(self, vehicle, timestep):
        pass

    # Vehicle drives according to set route and speed
    def drive(self, vehicle, timestep):
        route = vehicle.get_route()  # Sequence of (lon, lat)
        speed = vehicle.get_speed()
        dist_left = timestep * speed  # Remaining Distance
        rlats, rlons = zip(*([vehicle.get_location()] + route))  # New vehicle location after driving this route
        step_dist = geoutils.great_circle_distance(rlats[:-1], rlons[:-1], rlats[1:],
                                                   rlons[1:])  # Get distcnace in meters
        vehicle.state.travel_dist += dist_left

        for i, d in enumerate(step_dist):

            if dist_left < d:
                bearing = geoutils.bearing(rlats[i], rlons[i], rlats[i + 1], rlons[i + 1])  # Calculate angle of motion
                next_location = geoutils.end_location(rlats[i], rlons[i], dist_left, bearing)  # Calculate nxt location
                vehicle.update_location(next_location,
                                        route[i + 1:])  # Updating location based on route's nxt (lon, lat)
                return

            dist_left -= d

        if len(route) > 0:
            vehicle.update_location(route[-1], [])  # Go the last step


class Idle(VehicleBehavior):
    pass


class Cruising(VehicleBehavior):
    # Updated remaining time to destination, if arrived: state changes to parking
    def step(self, vehicle, timestep):
        arrived = vehicle.update_time_to_destination(timestep)
        if arrived:
            vehicle.park()
            return

        self.drive(vehicle, timestep)

# Dropoff one customer at a time + Update location and new route
class Occupied(VehicleBehavior):
    available = False
    # Updated remaining time to destination, if arrived customer gets off
    def step(self, vehicle, timestep):
        # arrived = vehicle.update_time_to_destination(timestep)
        arrived = False

        if vehicle.get_location() == vehicle.get_destination():
            arrived = True
            vehicle.state.accept_new_request = True
            self.available = True

            # print("Vid: ", vehicle.get_id(), " Occupied Dest: ", vehicle.get_destination())
            # print("Vid: ", vehicle.get_id(), "Arrived!")
        else:
            vehicle.state.accept_new_request = False

        if arrived:
            id = vehicle.ordered_pickups_dropoffs_ids.pop(0)  # POP HERE AND HEAD TO NEXT
            customer = simulator.models.customer.customer_repository.CustomerRepository.get(id)
            if vehicle.pickup_flags.pop(0) == 1:
                # print(vehicle.get_id(), "Occupied -> Pickup")
                vehicle.pickup(customer)  # At pickup, make the drop off plan (who gets dropped off first)
            else:
                vehicle.dropoff(customer)
            # env.models.customer.customer_repository.CustomerRepository.delete(customer.get_id())

        self.drive(vehicle, timestep)


# Pickup one customer at a time + Update location and new route
class Assigned(VehicleBehavior):
    available = False
    # Updated remaining time to destination, if arrived, update customer ID and picks him up
    def step(self, vehicle, timestep):
        # arrived = vehicle.update_time_to_destination(timestep)
        arrived = False

        if vehicle.get_location() == vehicle.get_destination():
            arrived = True
            # print("Vid: ", vehicle.get_id(), "Assigned", "Dest: ", vehicle.get_destination())
            # print("Vid: ", vehicle.get_id(), "Arrived ", arrived)

        if arrived:
            id = vehicle.ordered_pickups_dropoffs_ids.pop(0)    # POP HERE AND HEAD TO NEXT
            customer = simulator.models.customer.customer_repository.CustomerRepository.get(id)
            if vehicle.pickup_flags.pop(0) == 1:
                vehicle.pickup(customer)    # At pickup, make the drop off plan (who gets dropped off first)
            else:
                vehicle.dropoff(customer)

            # else:
            #     # print("Assigned, not pooling!")
            #     customer = simulator.models.customer.customer_repository.CustomerRepository.get(vehicle.get_assigned_customer_id())
            #     vehicle.pickup(customer)

        self.drive(vehicle, timestep)


class OffDuty(VehicleBehavior):
    available = False
    # Updated remaining time to destination, if returned state changes to parking
    def step(self, vehicle, timestep):
        returned = vehicle.update_time_to_destination(timestep)
        if returned:
            vehicle.park()
