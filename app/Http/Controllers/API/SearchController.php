<?php

namespace App\Http\Controllers\API;

use App\Classes\Encoding;
use App\Enums\BuyStatus;
use App\Enums\ReservationStatus;
use App\Enums\SettingsSystem;
use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\CheckBuyRequest;
use App\Http\Requests\SearchWeeklyScheduleRequest;
use App\Models\Buy;
use App\Models\Chairs;
use App\Models\Reservation;
use App\Models\WeeklySchedule;
use Carbon\Carbon;
use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class SearchController extends Controller
{
    /**
     * @OA\Get(
     *      path="/searches",
     *      operationId="searches",
     *      tags={"search"},
     *      summary="Get list of travells ",
     *      description="Returns json list of weekly schedule",
     *      @OA\Response(
     *          response=200,
     *          description="OK",
     *      ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found",
     *      ),
     *      @OA\Response(
     *          response=400,
     *          description="Http Bad Request",
     *      )
     * )
     */

    public function index(SearchWeeklyScheduleRequest $request): JsonResponse
    {
        if ($request->validated()){
            $source = $request->input("source");
            $destination = $request->input("destination");
            $max_date = Carbon::now()->addWeeks(SettingsSystem::Max_Week);
            $user_date = Carbon::parse($request->input("datetime"));
            if (!$user_date->gt($max_date)) {

                $weekly_schedule_city = WeeklySchedule::with("chairs")
                    ->where("source_city_id", $source)
                    ->where("destination_city_id", $destination)
                    ->whereDate("date", "=",$user_date)
                    ->get(["weekly_schedule.*", "chairs.id", "chairs.chairs"]);

                $weekly_schedule_terminal = WeeklySchedule::with("chairs")
                    ->where("source_terminal_id", $source)
                    ->where("destination_terminal_id", $destination)
                    ->whereDate("date", "=",$user_date)
                    ->get(["weekly_schedule.*", "chairs.id", "chairs.chairs"]);

                $data = array_unique($weekly_schedule_city->merge($weekly_schedule_terminal));
                if(count($data)>0){
                    $search_data = null;
                    foreach ($data as $item){
                        $search_data[] = ["search_code" => Encoding::base64url_encode($item["weekly_schedule.id"]."|".$item["chairs.id"]), "item" => $item];
                    }
                    return  response()->json($search_data)
                        ->setStatusCode(Response::HTTP_OK)
                        ->header('Content-Type', 'application/json');
                }else{
                    return response()
                        ->json(['status' => Status::UnSuccess , "code" => StatusCode::UnSuccess, "result" => "couldn't find bus with your order."])
                        ->setStatusCode(Response::HTTP_NOT_FOUND)
                        ->header('Content-Type', 'application/json');
                }
            } else {
                return response()
                    ->json(['status' => Status::UnSuccess , "code" => StatusCode::UnSuccess, "result" => " your date must be lower than ". $max_date])
                    ->setStatusCode(Response::HTTP_BAD_REQUEST)
                    ->header('Content-Type', 'application/json');
            }
        }else{
            return response()
                ->json(['status' => Status::Failed , "code" => StatusCode::HTTP_BAD_REQUEST])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }


    /**
     * @OA\Post(
     *      path="/extraditionBuy",
     *      operationId="extraditionBuyRequest",
     *      tags={"search"},
     *      summary="extradited a bougth",
     *      description="Returns json of result storing data",
     *       @OA\Parameter(
     *          description="action of oprations each of ['search', 'reserve', 'ticket']",
     *          in="path",
     *          name="action",
     *          required=true,
     *          @OA\Schema(type="string"),
     *      ),
     *      @OA\Parameter(
     *           description="a id of ticket bougth by user",
     *           in="path",
     *           name="ticket_id",
     *           @OA\Schema(type="integer"),
     *       ),
     *      @OA\Parameter(
     *           description="a id of reservation by user",
     *           in="path",
     *           name="reserve_id",
     *           @OA\Schema(type="integer"),
     *       ),
     *      @OA\Parameter(
     *           description="a hash of searchs by user",
     *           in="path",
     *           name="search_hash",
     *           @OA\Schema(type="string"),
     *       ),
     *      @OA\Response(
     *          response=200,
     *          description="checking",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Success",
     *                          "code":"1",
     *                          "data":"your bougth successfully extradited"
     *                     }
     *                 )
     *             )
     *         }
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Failed",
     *                          "code":"-1",
     *                          "data": "empty response, not found."
     *                     }
     *                 )
     *             )
     *         }
     *      ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data":"your request don't have some parameter."
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */
    public function check(CheckBuyRequest $request)
    {
        if ($request->validated()){
            switch ($request->input('action')){
                case "search":
                    $validated = $request->validate([
                        'search_hash' => 'required|string',
                    ],[
                        'search_hash.required' => 'destination must be required and lower than 5 char.'
                    ]);
                    if ($validated){
                        $search_id = explode('|',Encoding::base64url_decode($request->input("search_hash")));
                        $weekly_schedule = WeeklySchedule::find($search_id[0])->get();
                        $chair = Chairs::find($search_id[1])->get();
                        if (count($chair) > 0|| count($weekly_schedule) > 0){
                            return response()
                                ->json(['status' => Status::Success , "code" => StatusCode::Success, "result" => ["week" => $weekly_schedule,"chair" => $chair->chairs]])
                                ->setStatusCode(Response::HTTP_OK)
                                ->header('Content-Type', 'application/json');
                        }else {
                            return response()
                                ->json(['status' => Status::UnSuccess, "code" => StatusCode::UnSuccess, "result" => "couldn't find search with your order."])
                                ->setStatusCode(Response::HTTP_NOT_FOUND)
                                ->header('Content-Type', 'application/json');
                        }
                    }else{
                        return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> "your request don't have some parameter."])
                            ->setStatusCode(Response::HTTP_BAD_REQUEST)
                            ->header('Content-Type', 'application/json');
                    }
                case "reserve":
                    $validated = $request->validate([
                        'reserve_id' => 'required|integer',
                    ],[
                        'reserve_id.required' => 'reserve_id must be integer and required.'
                    ]);
                    if ($validated){
                        $reserve = Reservation::find($request->input("ticket_id"))->get();
                        if (count($reserve) > 0){
                            $status = "Success";
                            switch($reserve->status){
                                case ReservationStatus::Cancel:
                                    $status = "Cancel";
                                    break;
                                case ReservationStatus::Pending:
                                    $status = "Pending";
                                    break;
                                case ReservationStatus::Expired:
                                    $status = "Expired";
                                    break;
                            }
                            return response()
                                ->json([
                                    'status' => Status::Success,
                                    "code" => StatusCode::Success,
                                    "result" => [
                                        "travel" => $reserve->WeeklySchedule,
                                        "status"=> $status
                                    ]
                                ])
                                ->setStatusCode(Response::HTTP_OK)
                                ->header('Content-Type', 'application/json');
                        }else {
                            return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> null])
                                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                                ->header('Content-Type', 'application/json');
                        }
                    }else{
                        return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> null])
                            ->setStatusCode(Response::HTTP_BAD_REQUEST)
                            ->header('Content-Type', 'application/json');
                    }
                case "ticket":
                    $validated = $request->validate([
                        'reserve_id' => 'required|integer',
                    ],[
                        'reserve_id.required' => 'reserve_id must be integer and required.'
                    ]);
                    if ($validated){
                        $ticket = Buy::find($request->input("ticket_id"))->get();
                        if (count($ticket) > 0){
                            $reserve = $ticket->reserve();
                            return response()
                                ->json([
                                    'status' => Status::Success,
                                    "code" => StatusCode::Success,
                                    "result" => [
                                        "ticket" => $ticket->id,
                                        "passenger" => $ticket->passenger(),
                                        "travel" => $reserve->WeeklySchedule,
                                        "status"=> ($ticket->status == BuyStatus::Success? "Success":"Cancel")
                                    ]
                                ])
                                ->setStatusCode(Response::HTTP_OK)
                                ->header('Content-Type', 'application/json');
                        }else {
                            return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> null])
                                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                                ->header('Content-Type', 'application/json');
                        }
                    }else{
                        return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> null])
                            ->setStatusCode(Response::HTTP_BAD_REQUEST)
                            ->header('Content-Type', 'application/json');
                    }
            }
        }else{
            return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> null])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }
}
